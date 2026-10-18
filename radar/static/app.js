// radar/vagas: tela de busca. Tudo que vem da API é exibido como texto
// (textContent), nunca como HTML.

const $ = (sel) => document.querySelector(sel);
const NIVEIS = ["Estágio", "Júnior", "Pleno", "Sênior", "Lead/Staff", "Não informada"];
const MEU_FUSO = -new Date().getTimezoneOffset() / 60;
const STACKS_VISIVEIS = 18;

const PADRAO = {
  q: "", fuso: String(MEU_FUSO), tolerancia: 3, sem_fuso: true, sal_min: 0, sem_salario: false,
  stacks: [], senioridade: [], dias: "", fontes: [], so_tech: true, ordem: "recentes",
};

const estado = {
  filtros: { ...PADRAO },
  aba: "todas",
  pagina: 1,
  temMais: false,
  carregando: false,
  facetas: null,
  todasStacks: false,
  fontes: [],
  usdParaBrl: 5.5,
  seq: 0,
};

// ------------------------------------------------ localStorage (pode falhar em aba anônima)

const guarda = {
  ler(chave, padrao) {
    try { return JSON.parse(localStorage.getItem(chave)) ?? padrao; } catch { return padrao; }
  },
  gravar(chave, valor) {
    try { localStorage.setItem(chave, JSON.stringify(valor)); } catch { /* sem armazenamento, segue a vida */ }
  },
};
let favoritas = guarda.ler("radar:favoritas", {});
let ocultas = guarda.ler("radar:ocultas", {});

// ------------------------------------------------ filtros <-> URL

function paraParams(f) {
  const p = new URLSearchParams();
  if (f.q) p.set("q", f.q);
  if (f.fuso !== "") { p.set("fuso", f.fuso); p.set("tolerancia", f.tolerancia); }
  p.set("sem_fuso", f.sem_fuso ? 1 : 0);
  if (f.sal_min > 0) { p.set("sal_min", f.sal_min); p.set("sem_salario", f.sem_salario ? 1 : 0); }
  if (f.stacks.length) p.set("stacks", f.stacks.join(","));
  if (f.senioridade.length) p.set("senioridade", f.senioridade.join(","));
  if (f.dias) p.set("dias", f.dias);
  if (f.fontes.length) p.set("fontes", f.fontes.join(","));
  p.set("so_tech", f.so_tech ? 1 : 0);
  if (f.ordem !== "recentes") p.set("ordem", f.ordem);
  return p;
}

function deParams(p) {
  const lista = (k) => (p.get(k) || "").split(",").filter(Boolean);
  return {
    ...PADRAO,
    q: p.get("q") || "",
    fuso: p.has("fuso") ? p.get("fuso") : (p.has("so_tech") ? "" : PADRAO.fuso),
    tolerancia: Number(p.get("tolerancia") ?? PADRAO.tolerancia),
    sem_fuso: p.get("sem_fuso") !== "0",
    sal_min: Number(p.get("sal_min") || 0),
    sem_salario: p.get("sem_salario") === "1",
    stacks: lista("stacks"),
    senioridade: lista("senioridade"),
    dias: p.get("dias") || "",
    fontes: lista("fontes"),
    so_tech: p.get("so_tech") !== "0",
    ordem: p.get("ordem") || "recentes",
  };
}

// ------------------------------------------------ formatação

const SIMBOLO = { USD: "US$", EUR: "€", GBP: "£", BRL: "R$", CAD: "C$", AUD: "A$", INR: "₹" };
const POR = { ano: "/ano", mes: "/mês", hora: "/h", dia: "/dia", semana: "/sem" };
const compacto = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });
const reais = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });

function faixa(min, max, fmt) {
  if (!min || min === max) return fmt(max || min);
  return `${fmt(min)}–${fmt(max)}`;
}

function textoSalario(s) {
  const moeda = SIMBOLO[s.moeda] || `${s.moeda} `;
  const original = `${moeda} ${faixa(s.min, s.max, (v) => compacto.format(v))}${POR[s.periodo] || ""}`;
  const extras = [];
  if (s.usd_max && !(s.moeda === "USD" && s.periodo === "ano")) {
    extras.push(`≈ US$ ${faixa(s.usd_min, s.usd_max, (v) => compacto.format(v))}/ano`);
  }
  if (s.brl_mes_max) extras.push(`≈ R$ ${faixa(s.brl_mes_min, s.brl_mes_max, (v) => reais.format(v))}/mês`);
  return { original, extras: extras.join(" · ") };
}

function utc(o) {
  const sinal = o < 0 ? "−" : "+";
  const abs = Math.abs(o);
  const h = Math.floor(abs);
  return `${sinal}${h}${abs % 1 ? ":30" : ""}`;
}

function fusoCompativel(fuso, meu, tol) {
  if (fuso.tipo === "global") return true;
  return fuso.fusos.some((f) => Math.abs(f - meu) <= tol);
}

function quandoFoi(epoch) {
  const dias = Math.floor((Date.now() / 1000 - epoch) / 86400);
  if (dias <= 0) return "hoje";
  if (dias === 1) return "ontem";
  if (dias < 14) return `há ${dias} dias`;
  return `há ${Math.floor(dias / 7)} sem.`;
}

function haQuanto(epoch) {
  const min = Math.round((Date.now() / 1000 - epoch) / 60);
  if (min < 1) return "agora";
  if (min < 60) return `há ${min} min`;
  const h = Math.round(min / 60);
  return h < 48 ? `há ${h}h` : `há ${Math.round(h / 24)} dias`;
}

const linkSeguro = (url) => (/^https?:\/\//i.test(url || "") ? url : "#");

function el(tag, props = {}, ...filhos) {
  const e = document.createElement(tag);
  Object.assign(e, props);
  filhos.flat().forEach((f) => f != null && e.append(f));
  return e;
}

function aviso(msg) {
  document.querySelector(".aviso")?.remove();
  const a = el("div", { className: "aviso", role: "status", textContent: msg });
  document.body.append(a);
  setTimeout(() => a.remove(), 3200);
}

// ------------------------------------------------ card de vaga

function regua(fuso) {
  const r = document.createDocumentFragment();
  const f = estado.filtros;
  const meu = f.fuso === "" ? null : Math.round(Number(f.fuso));
  for (let o = -12; o <= 14; o++) {
    const i = document.createElement("i");
    if (fuso.tipo === "global" || fuso.fusos.some((x) => Math.abs(x - o) <= 0.5)) i.classList.add("aceito");
    if (meu !== null && o === meu) i.classList.add("meu");
    else if (meu !== null && Math.abs(o - meu) <= f.tolerancia) i.classList.add("perto");
    r.append(i);
  }
  return r;
}

function cardVaga(v) {
  const card = $("#tpl-vaga").content.firstElementChild.cloneNode(true);
  card.dataset.id = v.id;
  const url = linkSeguro(v.url);

  const logo = card.querySelector(".logo");
  const iniciais = (v.empresa.match(/\b\w/g) || ["?"]).slice(0, 2).join("").toUpperCase();
  logo.textContent = iniciais;
  if (v.logo) {
    const img = el("img", { alt: "", referrerPolicy: "no-referrer", hidden: true }); // sem lazy: escondida, nunca carregaria
    img.onerror = () => img.remove();
    img.onload = () => { logo.firstChild.remove(); img.hidden = false; };
    img.src = v.logo;
    logo.append(img);
  }

  const a = card.querySelector(".titulo a");
  a.href = url;
  a.textContent = v.titulo;
  if (v.nova) card.querySelector(".titulo").append(el("span", { className: "nova", textContent: "NOVA" }));

  const meta = card.querySelector(".meta");
  meta.append(el("b", { textContent: v.empresa }));
  [v.senioridade, v.tipo, v.local && v.local.length < 60 ? v.local : null, quandoFoi(v.publicada_em)]
    .filter(Boolean).forEach((t) => meta.append(` · ${t}`));

  const tags = card.querySelector(".tags");
  v.stacks.slice(0, 10).forEach((s) => {
    tags.append(el("li", { textContent: s, className: estado.filtros.stacks.includes(s) ? "marcada" : "" }));
  });

  const sal = card.querySelector(".salario");
  if (v.salario) {
    const { original, extras } = textoSalario(v.salario);
    sal.append(original);
    if (extras) sal.append(" ", el("small", { textContent: extras }));
  } else {
    sal.classList.add("vazio");
    sal.textContent = "salário não informado";
  }

  card.querySelector(".regua").append(regua(v.fuso));
  const ft = card.querySelector(".fuso-txt");
  if (v.fuso.tipo === "global") ft.textContent = "qualquer fuso";
  else if (v.fuso.tipo === "desconhecido") ft.textContent = "fuso não informado";
  else {
    const fs = v.fuso.fusos;
    let txt = fs.length === 1 ? `UTC${utc(fs[0])}` : `UTC${utc(fs[0])} a ${utc(fs[fs.length - 1])}`;
    if (fs.length >= 20) txt = "praticamente qualquer fuso";
    ft.textContent = txt + (v.fuso.tipo === "estimado" ? " (estimado)" : "");
  }
  const f = estado.filtros;
  if (f.fuso !== "" && v.fuso.tipo !== "desconhecido") {
    const ok = fusoCompativel(v.fuso, Number(f.fuso), f.tolerancia);
    ft.append(" ", el("span", { className: ok ? "ok" : "nao", textContent: ok ? "✓ bate com o seu" : "fora do seu fuso" }));
  }

  card.querySelector(".resumo").textContent = v.resumo;
  card.querySelector(".via").append(
    "via ", el("b", { textContent: v.fonte }), " · ",
    el("a", { href: url, target: "_blank", rel: "noopener", textContent: "ver vaga original ↗" }),
  );

  const fav = card.querySelector(".fav");
  const ehFav = Boolean(favoritas[v.id]);
  fav.setAttribute("aria-pressed", ehFav);
  fav.setAttribute("aria-label", ehFav ? "Tirar dos favoritos" : "Favoritar");
  fav.title = fav.getAttribute("aria-label");
  fav.onclick = () => {
    if (favoritas[v.id]) delete favoritas[v.id]; else favoritas[v.id] = v;
    guarda.gravar("radar:favoritas", favoritas);
    contadores();
    if (estado.aba === "favoritas") card.remove();
    else {
      fav.setAttribute("aria-pressed", Boolean(favoritas[v.id]));
      fav.setAttribute("aria-label", favoritas[v.id] ? "Tirar dos favoritos" : "Favoritar");
    }
  };

  const ocu = card.querySelector(".ocu");
  const ehOculta = Boolean(ocultas[v.id]);
  ocu.textContent = ehOculta ? "↺" : "✕";
  ocu.setAttribute("aria-label", ehOculta ? "Mostrar de novo" : "Ocultar esta vaga");
  ocu.title = ocu.getAttribute("aria-label");
  ocu.onclick = () => {
    if (ocultas[v.id]) delete ocultas[v.id]; else ocultas[v.id] = v;
    guarda.gravar("radar:ocultas", ocultas);
    contadores();
    card.remove();
  };
  return card;
}

// ------------------------------------------------ busca

async function buscar({ mais = false } = {}) {
  if (estado.aba !== "todas") return mostrarGuardadas();
  const seq = ++estado.seq;
  estado.pagina = mais ? estado.pagina + 1 : 1;
  estado.carregando = true;
  const params = paraParams(estado.filtros);
  history.replaceState(null, "", `?${params}`);
  params.set("pagina", estado.pagina);

  const lista = $("#lista");
  if (!mais) {
    lista.replaceChildren(...Array.from({ length: 4 }, () => el("li", { className: "esqueleto", ariaHidden: "true" })));
  }
  $("#fim").textContent = mais ? "carregando…" : "";
  try {
    const resp = await fetch(`/api/vagas?${params}`);
    const dados = await resp.json();
    if (seq !== estado.seq) return; // chegou a resposta de uma busca antiga
    estado.temMais = dados.tem_mais;
    estado.facetas = dados.facetas;
    if (!mais) lista.replaceChildren();
    dados.vagas.filter((v) => !ocultas[v.id]).forEach((v) => lista.append(cardVaga(v)));
    $("#contagem").replaceChildren(
      el("b", { textContent: dados.total.toLocaleString("pt-BR") }),
      ` ${dados.total === 1 ? "vaga encontrada" : "vagas encontradas"}`,
      dados.total ? ` · ${dados.facetas.com_salario} com salário informado` : "",
    );
    if (!dados.total) {
      lista.append(el("li", { className: "vazio-lista", textContent: "Nenhuma vaga com esses filtros. Tente aumentar a tolerância de fuso, baixar o salário mínimo ou desmarcar alguma stack." }));
    }
    $("#fim").textContent = !dados.total ? "" : (estado.temMais ? "" : "fim da lista ✦");
    desenhaFacetas();
  } catch (erro) {
    if (seq !== estado.seq) return;
    lista.replaceChildren(el("li", { className: "vazio-lista", textContent: "Não consegui falar com o servidor. Tenta de novo em instantes." }));
    console.error(erro);
  } finally {
    if (seq === estado.seq) estado.carregando = false;
  }
}

function mostrarGuardadas() {
  const fonte = estado.aba === "favoritas" ? favoritas : ocultas;
  const vagas = Object.values(fonte).sort((a, b) => b.publicada_em - a.publicada_em);
  const lista = $("#lista");
  lista.replaceChildren(...vagas.map(cardVaga));
  const nome = estado.aba === "favoritas" ? "favorita" : "oculta";
  $("#contagem").replaceChildren(el("b", { textContent: vagas.length }), ` ${nome}${vagas.length === 1 ? "" : "s"} · ficam salvas só neste navegador`);
  if (!vagas.length) {
    lista.append(el("li", {
      className: "vazio-lista",
      textContent: estado.aba === "favoritas" ? "Clique na ★ de uma vaga para guardar aqui." : "Vagas que você ocultar (✕) aparecem aqui.",
    }));
  }
  $("#fim").textContent = "";
}

function contadores() {
  const nf = Object.keys(favoritas).length;
  const no = Object.keys(ocultas).length;
  $("#n-fav").textContent = nf ? `(${nf})` : "";
  $("#n-ocu").textContent = no ? `(${no})` : "";
}

// ------------------------------------------------ painel de filtros

function chip(texto, qtd, marcado, aoClicar) {
  const b = el("button", { type: "button", className: "chip", onclick: aoClicar }, texto);
  if (qtd != null) b.append(el("small", { textContent: qtd }));
  b.setAttribute("aria-pressed", marcado);
  return b;
}

function alterna(lista, item) {
  return lista.includes(item) ? lista.filter((x) => x !== item) : [...lista, item];
}

function desenhaFacetas() {
  const f = estado.filtros;
  const fac = estado.facetas || { stacks: [], senioridade: [], fontes: [] };

  const contagem = new Map(fac.stacks);
  const nomes = [...f.stacks, ...fac.stacks.map(([s]) => s).filter((s) => !f.stacks.includes(s))];
  const visiveis = estado.todasStacks ? nomes : nomes.slice(0, Math.max(STACKS_VISIVEIS, f.stacks.length));
  $("#stacks").replaceChildren(...visiveis.map((s) => chip(s, contagem.get(s) ?? 0, f.stacks.includes(s), () => {
    f.stacks = alterna(f.stacks, s);
    buscar();
  })));
  $("#mais-stacks").hidden = nomes.length <= STACKS_VISIVEIS;
  $("#mais-stacks").textContent = estado.todasStacks ? "ver menos" : `ver mais (${nomes.length - visiveis.length})`;

  const porNivel = new Map(fac.senioridade);
  $("#senioridade").replaceChildren(...NIVEIS.map((n) => chip(n, porNivel.get(n) ?? 0, f.senioridade.includes(n), () => {
    f.senioridade = alterna(f.senioridade, n);
    buscar();
  })));

  const porFonte = new Map(fac.fontes);
  $("#fontes").replaceChildren(...estado.fontes.map((fo) => {
    const marcada = !f.fontes.length || f.fontes.includes(fo.nome);
    const input = el("input", { type: "checkbox", checked: marcada });
    input.onchange = () => {
      const todas = estado.fontes.map((x) => x.nome);
      let sel = f.fontes.length ? f.fontes : todas;
      sel = alterna(sel, fo.nome);
      f.fontes = sel.length === todas.length ? [] : sel;
      buscar();
    };
    const info = fo.ok === 0
      ? el("small", { className: "erro", textContent: "fora do ar", title: fo.erro || "" })
      : el("small", { textContent: porFonte.get(fo.nome) ?? 0 });
    return el("label", { className: "check" }, el("span", {}, input, fo.nome), info);
  }));
}

function textoSalarioMin(v) {
  if (!v) return "qualquer valor";
  const brlMes = Math.round((v * estado.usdParaBrl) / 12);
  return `US$ ${compacto.format(v)}/ano · ≈ R$ ${reais.format(brlMes)}/mês`;
}

function preencheControles() {
  const f = estado.filtros;
  $("#q").value = f.q;
  $("#fuso").value = f.fuso;
  $("#tolerancia").value = f.tolerancia;
  $("#tolerancia-valor").textContent = `±${f.tolerancia}h`;
  $("#linha-tolerancia").hidden = f.fuso === "";
  $("#sem_fuso").checked = f.sem_fuso;
  $("#sal_min").value = f.sal_min;
  $("#sal-valor").textContent = textoSalarioMin(f.sal_min);
  $("#sem_salario").checked = f.sem_salario;
  $("#dias").value = f.dias;
  $("#so_tech").checked = f.so_tech;
  $("#ordem").value = f.ordem;
  desenhaFacetas();
}

function montaSelectFuso() {
  const s = $("#fuso");
  s.append(el("option", { value: "", textContent: "qualquer fuso" }));
  for (let o = -12; o <= 14; o++) {
    const nomes = { "-3": " (Brasília)", "-5": " (Nova York)", "-8": " (Califórnia)", 0: " (Londres)", 1: " (Berlim)", "5.5": " (Índia)" };
    s.append(el("option", { value: String(o), textContent: `UTC${o === 0 ? "" : utc(o)}${nomes[o] || ""}${o === Math.round(MEU_FUSO) ? " ← você" : ""}` }));
  }
}

let espera;
function ligaControles() {
  const f = estado.filtros;
  const depois = (fn, ms = 250) => { clearTimeout(espera); espera = setTimeout(fn, ms); };

  $("#q").oninput = (e) => { f.q = e.target.value.trim(); depois(buscar); };
  $("#fuso").onchange = (e) => { f.fuso = e.target.value; preencheControles(); buscar(); };
  $("#tolerancia").oninput = (e) => {
    f.tolerancia = Number(e.target.value);
    $("#tolerancia-valor").textContent = `±${f.tolerancia}h`;
    depois(buscar);
  };
  $("#sem_fuso").onchange = (e) => { f.sem_fuso = e.target.checked; buscar(); };
  $("#sal_min").oninput = (e) => {
    f.sal_min = Number(e.target.value);
    $("#sal-valor").textContent = textoSalarioMin(f.sal_min);
    depois(buscar);
  };
  $("#sem_salario").onchange = (e) => { f.sem_salario = e.target.checked; buscar(); };
  $("#dias").onchange = (e) => { f.dias = e.target.value; buscar(); };
  $("#so_tech").onchange = (e) => { f.so_tech = e.target.checked; buscar(); };
  $("#ordem").onchange = (e) => { f.ordem = e.target.value; buscar(); };
  $("#mais-stacks").onclick = () => { estado.todasStacks = !estado.todasStacks; desenhaFacetas(); };

  $("#salvar").onclick = () => {
    guarda.gravar("radar:meu-filtro", paraParams(f).toString());
    aviso("Filtro salvo. O radar vai abrir sempre assim.");
  };
  $("#limpar").onclick = () => {
    estado.filtros = { ...PADRAO, stacks: [], senioridade: [], fontes: [] };
    ligaControles();
    preencheControles();
    buscar();
  };

  document.querySelectorAll(".aba").forEach((b) => {
    b.onclick = () => {
      estado.aba = b.dataset.aba;
      document.querySelectorAll(".aba").forEach((x) => x.setAttribute("aria-pressed", x === b));
      buscar();
    };
  });

  const painel = $("#filtros");
  const abre = (sim) => {
    painel.classList.toggle("aberto", sim);
    $("#abrir-filtros").setAttribute("aria-expanded", sim);
  };
  $("#abrir-filtros").onclick = () => abre(true);
  $("#fechar-filtros").onclick = () => abre(false);
}

// ------------------------------------------------ status e atualização

async function atualizaStatus() {
  const s = await fetch("/api/status").then((r) => r.json());
  estado.fontes = s.fontes;
  estado.usdParaBrl = s.usd_para_brl;
  $("#sal-valor").textContent = textoSalarioMin(estado.filtros.sal_min);
  const st = $("#status");
  if (s.coletando) {
    st.replaceChildren(el("span", { className: "pulso", textContent: "● " }), "buscando vagas novas…");
  } else {
    const quando = s.ultima_coleta ? `atualizado ${haQuanto(s.ultima_coleta)}` : "ainda sem coleta";
    st.textContent = `${s.total.toLocaleString("pt-BR")} vagas · ${s.fontes.length} fontes · ${quando}`;
  }
  $("#atualizar").disabled = s.coletando;
  $("#creditos").replaceChildren(...s.fontes.flatMap((fo, i) => [
    i ? (i === s.fontes.length - 1 ? " e " : ", ") : "",
    el("a", { href: fo.site, target: "_blank", rel: "noopener", textContent: fo.nome }),
  ]));
  desenhaFacetas();
  return s;
}

async function esperaColeta() {
  const s = await atualizaStatus();
  if (s.coletando) setTimeout(esperaColeta, 4000);
  else buscar();
}

$("#atualizar").onclick = async () => {
  const r = await fetch("/api/atualizar", { method: "POST" });
  const dados = await r.json();
  aviso(dados.motivo);
  if (r.ok) setTimeout(esperaColeta, 1000);
};

// ------------------------------------------------ início

function iniciar() {
  montaSelectFuso();
  const daUrl = new URLSearchParams(location.search);
  const salvo = guarda.ler("radar:meu-filtro", null);
  if ([...daUrl.keys()].length) estado.filtros = deParams(daUrl);
  else if (salvo) estado.filtros = deParams(new URLSearchParams(salvo));
  ligaControles();
  preencheControles();
  contadores();

  new IntersectionObserver((itens) => {
    if (itens[0].isIntersecting && estado.temMais && !estado.carregando && estado.aba === "todas") buscar({ mais: true });
  }, { rootMargin: "400px" }).observe($("#fim"));

  atualizaStatus().then((s) => (s.coletando ? setTimeout(esperaColeta, 4000) : null));
  buscar();
}

iniciar();
