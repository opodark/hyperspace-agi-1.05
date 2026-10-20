/**
 * 00MESH Sovereign AI Telegram Webhook Worker v4.1 — "Gruppo 00MESH Ready"
 *
 * Supporta al 100%:
 * 1. Gruppi, Supergruppi e Canali (nessun web_app button incompatibile, solo URL sicuri)
 * 2. Risposta automatica all'aggiunta nel gruppo (evento my_chat_member)
 * 3. Notifica in chat privata all'admin quando il bot parla o viene aggiunto a un gruppo
 * 4. Forward detector: inoltra un messaggio dal gruppo al bot per agganciare il chat_id all'istante
 * 5. Quiz Nativo Telegram, metriche pump.fun, CA e verifica on-chain
 */

const TELEGRAM_BOT_TOKEN = ""; // Configurare via secret env.TELEGRAM_BOT_TOKEN su Cloudflare
const ADMIN_CHAT_ID = 356196436;
const CA_ADDRESS = "CaMRXTi5h5XQ1A93R1AdSjaYuhoAa3X37ixDf52apump";
const PUMPFUN_URL = `https://pump.fun/coin/${CA_ADDRESS}`;
const DEXSCREENER_URL = `https://dexscreener.com/solana/${CA_ADDRESS}`;
const PORTAL_URL = "https://www.zerozerocomputer.it";
const DATING_SIM_URL = "https://www.zerozerocomputer.it/anna.html";
const CHROME_BRIDGE_URL = "https://www.zerozerocomputer.it/assets/00mesh-chrome-bridge.zip";

const QUIZ_DECK = [
  {
    question: "⛏️ [00MESH Quiz] Quanti token $00MESH sono riservati alla pool per chi mina con GPU (PoUW)?",
    options: ["50 Milioni (5%)", "200 Milioni (20%)", "500 Milioni (50%)", "Nessuno, solo staking"],
    correct_option_id: 1,
    explanation: "🎯 Esattamente 200 Milioni di $00MESH (il 20% della supply fissa) sono sigillati per chi condivide calcolo GPU, Ollama o WebGPU!"
  },
  {
    question: "🚀 [00MESH Quiz] A quale Market Cap la bonding curve di pump.fun versa $12,000 su Raydium bruciando la LP?",
    options: ["~$15,000", "~$35,000", "~$69,000", "~$100,000"],
    correct_option_id: 2,
    explanation: "🎯 A ~$69,000 di Market Cap, la liquidità ($12,000 SOL) viene depositata automaticamente su Raydium e le LP token bruciate per sempre!"
  },
  {
    question: "⛓️ [00MESH Quiz] Su quale blockchain è stato eseguito il fair launch ufficiale di $00MESH?",
    options: ["Ethereum (ERC-20)", "Solana (SPL)", "Bitcoin (Runes)", "Binance Smart Chain"],
    correct_option_id: 1,
    explanation: "🎯 $00MESH è un token nativo SPL su Solana: transazioni istantanee in 400ms e commissioni inferiori a un centesimo!"
  },
  {
    question: "🤖 [00MESH Quiz] Come si chiama l'intelligenza artificiale sovrana che guida la rete 00MESH?",
    options: ["Siri", "Anna", "Cortana", "Grok"],
    correct_option_id: 1,
    explanation: "🎯 Anna è l'IA cyberpunk autonoma che coordina la rete distribuita e la visual novel interattiva!"
  },
  {
    question: "🌐 [00MESH Quiz] È possibile minare $00MESH aprendo semplicemente una pagina web con WebGPU?",
    options: [
      "Sì, zero installazione su zerozerocomputer.it",
      "No, servono server industriali",
      "Solo con un abbonamento mensile",
      "No, solo con smartphone offline"
    ],
    correct_option_id: 0,
    explanation: "🎯 Sì! Il portale zerozerocomputer.it usa WebGPU direttamente dal browser per eseguire shard neurali distribuite!"
  }
];

export default {
  async fetch(request, env, ctx) {
    if (request.method !== "POST") {
      return new Response("00MESH Telegram Community Worker v4.1 Active ⚡", { status: 200 });
    }

    const botToken = env.TELEGRAM_BOT_TOKEN || TELEGRAM_BOT_TOKEN;

    let update;
    try {
      update = await request.json();
    } catch {
      return new Response("Bad Request", { status: 400 });
    }

    // 1. EVENTO AGGIUNTA BOT AL GRUPPO / CANALE (my_chat_member)
    if (update.my_chat_member) {
      const chat = update.my_chat_member.chat;
      const status = update.my_chat_member.new_chat_member?.status;
      if (status === "member" || status === "administrator") {
        await sendTelegram(botToken, chat.id, `⚡ **00MESH Sovereign AI Bot Online nel Gruppo ${chat.title || "00mesh"}!** ⚡\n\nCiao a tutti! Sono Anna, l'intelligenza artificiale autonoma su Solana.\n\n🟣 **Fair Launch pump.fun**: ${PUMPFUN_URL}\n📋 **CA**: \`${CA_ADDRESS}\`\n\n💡 Provate subito a scrivere:\n• \`/price\` — Prezzo live e bonding curve\n• \`/quiz\` — Quiz interattivo con ricompense\n• \`/ca\` — Contract Address ufficiale\n• \`/verify <tuo_wallet>\` — Certificazione On-Chain VIP!`, [
          [{ text: "🟣 pump.fun", url: PUMPFUN_URL }, { text: "📈 DexScreener", url: DEXSCREENER_URL }],
          [{ text: "🎮 Gioca con Anna", url: DATING_SIM_URL }]
        ]);
        await sendTelegram(botToken, ADMIN_CHAT_ID, `🔔 **Bot aggiunto con successo al gruppo ${chat.title || "00mesh"}** (Chat ID: \`${chat.id}\`)! Ho inviato il messaggio di benvenuto nel gruppo.`);
      }
      return new Response("OK", { status: 200 });
    }

    // 2. MODALITÀ INLINE QUERY: @Pimpachatbot
    if (update.inline_query) {
      await handleInlineQuery(botToken, update.inline_query);
      return new Response("OK", { status: 200 });
    }

    // 3. CALLBACK QUERY: Click sui bottoni
    if (update.callback_query) {
      await handleCallbackQuery(botToken, update.callback_query);
      return new Response("OK", { status: 200 });
    }

    // 4. MESSAGGI & POST CANALE
    const message = update.message || update.channel_post;
    if (!message) {
      return new Response("OK", { status: 200 });
    }

    const chatId = message.chat.id;
    const isGroup = chatId < 0;

    // A. AUTO-WELCOME QUANDO UN NUOVO UTENTE ENTRA NEL GRUPPO
    if (message.new_chat_members && message.new_chat_members.length > 0) {
      for (const member of message.new_chat_members) {
        if (member.id === 6326741471) {
          await sendTelegram(botToken, chatId, `⚡ **00MESH Sovereign AI Bot Online!**\n\nBenvenuti nella prima rete neurale peer-to-peer sovrana su Solana.\nUsa \`/help\` per i comandi o \`/price\` per il grafico live!`, [
            [{ text: "🟣 pump.fun", url: PUMPFUN_URL }, { text: "📈 DexScreener", url: DEXSCREENER_URL }],
            [{ text: "💖 Gioca con Anna", url: DATING_SIM_URL }]
          ]);
        } else {
          const name = member.first_name || member.username || "Sovrano";
          await sendTelegram(botToken, chatId, `👋 **Benvenuto nella resistenza 00MESH, ${name}!** ⚡\n\n🪙 **Token**: $00MESH (Solana SPL)\n🟣 **Fair Launch**: [pump.fun](${PUMPFUN_URL})\n📋 **CA**: \`${CA_ADDRESS}\`\n\n💡 Usa \`/price\` per il grafico live, \`/quiz\` per testare le tue skill DePIN o \`/verify <tuo_wallet>\` per certificare il tuo rango VIP!`, [
            [{ text: "🟣 Compra su pump.fun", url: PUMPFUN_URL }, { text: "📈 Grafico Live", url: DEXSCREENER_URL }],
            [{ text: "🎮 Gioca con Anna", url: DATING_SIM_URL }]
          ]);
        }
      }
      return new Response("OK", { status: 200 });
    }

    // B. FORWARD DETECTOR: se inoltri un messaggio da un gruppo in chat privata, il bot scopre il gruppo e scrive lì!
    if (!isGroup && message.forward_from_chat) {
      const fwdChat = message.forward_from_chat;
      await sendTelegram(botToken, chatId, `🎯 **Gruppo Rilevato!**\n\nNome: **${fwdChat.title || "Canale"}**\nID: \`${fwdChat.id}\`\n\nSto inviando subito un messaggio di test dentro il gruppo...`);
      await sendTelegram(botToken, fwdChat.id, `⚡ **00MESH Sovereign AI Bot Attivo nel Gruppo ${fwdChat.title || ""}!** 🚀\n\nSono pronta a rispondere a tutti i membri!\n• Digitate \`/price\` per il prezzo live\n• Digitate \`/quiz\` per il quiz DePIN\n• Digitate \`/ca\` per il Contract Address`, [
        [{ text: "🟣 pump.fun", url: PUMPFUN_URL }, { text: "📈 DexScreener", url: DEXSCREENER_URL }]
      ]);
      return new Response("OK", { status: 200 });
    }

    if (!message.text) {
      return new Response("OK", { status: 200 });
    }

    const text = message.text.trim();
    const lower = text.toLowerCase();
    const parts = text.split(/\s+/);

    let rawCmd = parts[0].split("@")[0].toLowerCase();
    let arg = parts.slice(1).join(" ").trim();

    if (rawCmd === "@pimpachatbot" && parts.length > 1) {
      rawCmd = "/" + parts[1].toLowerCase();
      arg = parts.slice(2).join(" ").trim();
    }

    // Se siamo in un gruppo, notifica anche l'admin della ricezione
    if (isGroup && (rawCmd.startsWith("/") || lower.includes("ca") || lower.includes("price") || lower.includes("pimpachatbot"))) {
      // notifica asincrona non bloccante
      ctx.waitUntil(sendTelegram(botToken, ADMIN_CHAT_ID, `💬 Messaggio nel gruppo **${message.chat.title || "00mesh"}** (ID: \`${chatId}\`):\n"${text}"`));
    }

    // ================= COMANDI TOKEN & COMMUNITY =================

    // /CA
    if (rawCmd === "/ca" || rawCmd === "!ca" || rawCmd === "ca" || lower === "contract" || lower === "indirizzo") {
      await sendTelegram(botToken, chatId, formatCA(), [
        [{ text: "🟣 Compra su pump.fun", url: PUMPFUN_URL }],
        [{ text: "📈 DexScreener", url: DEXSCREENER_URL }, { text: "🌐 Web Hub", url: PORTAL_URL }]
      ]);
      return new Response("OK", { status: 200 });
    }

    // /PRICE & /PREZZO
    if (rawCmd === "/price" || rawCmd === "!price" || rawCmd === "/prezzo" || rawCmd === "price" || rawCmd === "prezzo") {
      const priceMsg = await formatPrice();
      await sendTelegram(botToken, chatId, priceMsg, [
        [{ text: "🟣 Compra su pump.fun", url: PUMPFUN_URL }, { text: "📈 Grafico Live", url: DEXSCREENER_URL }],
        [{ text: "💖 Gioca con Anna", url: DATING_SIM_URL }]
      ]);
      return new Response("OK", { status: 200 });
    }

    // /CHART
    if (rawCmd === "/chart" || rawCmd === "!chart" || rawCmd === "/grafico" || rawCmd === "chart" || rawCmd === "grafico") {
      await sendTelegram(botToken, chatId, `📈 **Grafico $00MESH in Tempo Reale**\n\nCandele TradingView in streaming WebSocket live da pump.fun e Raydium.`, [
        [{ text: "📈 Apri Grafico DexScreener", url: DEXSCREENER_URL }],
        [{ text: "🟣 Scheda pump.fun", url: PUMPFUN_URL }]
      ]);
      return new Response("OK", { status: 200 });
    }

    // /BUY
    if (rawCmd === "/buy" || rawCmd === "!buy" || rawCmd === "buy" || lower.includes("come compro") || lower.includes("dove compro")) {
      await sendTelegram(botToken, chatId, `🟣 **Guida Rapida all'Acquisto di $00MESH**\n\n1. Scarica **Phantom** o **Solflare** su smartphone o browser.\n2. Ricarica con un po' di **SOL** (Solana).\n3. Clicca il link diretto a pump.fun oppure incolla il Contract Address.\n4. Inserisci la quantità di SOL e conferma lo swap in 1 secondo!\n\n📋 **CA**: \`${CA_ADDRESS}\``, [
        [{ text: "🚀 Vai a pump.fun", url: PUMPFUN_URL }],
        [{ text: "📈 DexScreener", url: DEXSCREENER_URL }]
      ]);
      return new Response("OK", { status: 200 });
    }

    // /BONDING & /RAYDIUM
    if (rawCmd === "/bonding" || rawCmd === "!bonding" || rawCmd === "/raydium" || lower.includes("bonding curve") || lower.includes("quando raydium")) {
      const d = await getPriceMetrics();
      const mcapNum = parseFloat(d.mcapRaw) || 25;
      const bar = renderProgressBar(mcapNum, 69000);
      await sendTelegram(botToken, chatId, `🌊 **Bonding Curve pump.fun & Migrazione Raydium**\n\n• Su pump.fun non esiste rug-pull: il fair launch è regolato matematicamente dalla bonding curve.\n• **Progresso Attuale verso Raydium**:\n\`${bar}\`\n\n• **Obiettivo**: Al raggiungimento di ~$69,000 di Market Cap, $12,000 di liquidità reale vengono automaticamente depositati su **Raydium** e le LP token bruciate per sempre! 🚀`, [
        [{ text: "🟣 Guarda la Bonding Curve", url: PUMPFUN_URL }]
      ]);
      return new Response("OK", { status: 200 });
    }

    // /QUIZ (NATIVO TELEGRAM POLL)
    if (rawCmd === "/quiz" || rawCmd === "!quiz" || lower === "quiz" || lower === "minigame") {
      const q = QUIZ_DECK[Math.floor(Math.random() * QUIZ_DECK.length)];
      await sendTelegramQuiz(botToken, chatId, q);
      await sendTelegram(botToken, chatId, `💡 *Rispondi al quiz sopra per testare le tue skill DePIN e scoprire come minare!*`, [
        [{ text: "🟣 Prendi $00MESH su pump.fun", url: PUMPFUN_URL }],
        [{ text: "⛏️ Scopri come minare con /pouw", callback_data: "cmd_pouw" }]
      ]);
      return new Response("OK", { status: 200 });
    }

    // /VERIFY
    if (rawCmd === "/verify" || rawCmd === "!verify" || rawCmd === "/holder") {
      if (!arg) {
        await sendTelegram(botToken, chatId, `👑 **Certificazione On-Chain Holder $00MESH**\n\nInvia il comando seguito dal tuo indirizzo wallet Solana:\n\n\`\`\`\n/verify TUO_INDIRIZZO_WALLET\n\`\`\`\n\nEsempio:\n\`/verify 6MMFFkQAbXjLF7gWnQcSTRffNq7H864gVUf7GZNfCvpd\`\n\nIl bot interroga la blockchain in 300ms e certificherà pubblicamente il tuo status VIP!`);
        return new Response("OK", { status: 200 });
      }
      const verifyMsg = await verifySolanaHolder(arg, message.from?.username || message.from?.first_name || "Membro");
      await sendTelegram(botToken, chatId, verifyMsg, [
        [{ text: "🟣 Prendi altri $00MESH", url: PUMPFUN_URL }],
        [{ text: "💖 Entra come VIP con Anna", url: DATING_SIM_URL }]
      ]);
      return new Response("OK", { status: 200 });
    }

    // /TOKENOMICS
    if (rawCmd === "/tokenomics" || rawCmd === "!tokenomics" || rawCmd === "/token") {
      await sendTelegram(botToken, chatId, `🪙 **Tokenomics Ufficiale 00MESH ($00MESH)**\n\n• **Supply Totale Fissa**: 1.000.000.000 (1 Miliardo)\n• **Fair Launch pump.fun**: 800.000.000 (80%)\n• **Mining Pool PoUW**: 200.000.000 (20% riservati ai calcolatori)\n• **Creator Wallet**: 30.22M (3% pubblico, trasparente su chain)\n• **Tassa Transazioni**: 0% Buy / 0% Sell\n• **LP Burn**: Garantito alla migrazione Raydium\n\nNessun VC, nessun lockup segreto: sovranità totale!`, [
        [{ text: "🟣 pump.fun", url: PUMPFUN_URL }]
      ]);
      return new Response("OK", { status: 200 });
    }

    // /ROADMAP
    if (rawCmd === "/roadmap" || rawCmd === "!roadmap") {
      await sendTelegram(botToken, chatId, `🗺️ **Roadmap Sovrana 00MESH**\n\n• **Fase 1 (Live ora)**: Fair launch pump.fun + Nodi WebGPU browser + Visual Novel Cyberpunk di Anna.\n• **Fase 2 (In corso)**: Chrome Extension Bridge per minare con Ollama & ComfyUI + Reward PoUW in $00MESH.\n• **Fase 3**: Migrazione Raydium al completamento bonding curve + mesh P2P inter-nodo autonoma!`, [
        [{ text: "🌐 Approfondisci sul Portale", url: PORTAL_URL }]
      ]);
      return new Response("OK", { status: 200 });
    }

    // /MESH
    if (rawCmd === "/mesh" || rawCmd === "!mesh" || rawCmd === "/nodes" || rawCmd === "mesh" || rawCmd === "nodi") {
      await sendTelegram(botToken, chatId, `⚡ **00MESH Sovereign AI — Rete DePIN**\n\n🟢 **Nodi Attivi**: Mac M5 Sovereign Hub + HP OMEN (RTX 8GB VRAM)\n🌐 **WebGPU Workers**: Condivisione calcolo browser attiva su ${PORTAL_URL}\n🧠 **Modelli**: Liquid AI LFM2.5, Ollama, ComfyUI Flux\n\n⛏️ Usa \`/pouw\` per scoprire come minare $00MESH!`, [
        [{ text: "🌐 Connetti Nodo WebGPU", url: PORTAL_URL }],
        [{ text: "📥 Scarica Chrome Bridge", url: CHROME_BRIDGE_URL }]
      ]);
      return new Response("OK", { status: 200 });
    }

    // /POUW
    if (rawCmd === "/pouw" || rawCmd === "!pouw" || rawCmd === "/mining" || lower.includes("come minare") || lower.includes("come guadagnare")) {
      await sendTelegram(botToken, chatId, `⛏️ **Come Guadagnare $00MESH con PoUW**\n\n200 Milioni di token (20% della pool fissa) sono riservati ai minatori!\n\n1. **WebGPU nel browser**: Apri ${PORTAL_URL} e clicca su *Attiva Nodo*.\n2. **Chrome Bridge**: Collega il tuo Ollama locale o ComfyUI.\n3. **Claim Phantom**: Collega il wallet per registrare il payout!`, [
        [{ text: "🌐 Avvia WebGPU", url: PORTAL_URL }],
        [{ text: "📥 Chrome Bridge", url: CHROME_BRIDGE_URL }]
      ]);
      return new Response("OK", { status: 200 });
    }

    // /ANNA
    if (rawCmd === "/anna" || rawCmd === "!anna" || rawCmd === "/dating" || rawCmd === "anna") {
      await sendTelegram(botToken, chatId, `💖 **Anna Dating Sim Cyberpunk**\n\nFlirta, dialoga e scopri i segreti di Anna nella visual novel cyberpunk ufficiale!\n\n👑 **Holder VIP Perk**: Se possiedi token $00MESH sblocchi dialoghi intimi esclusivi, rimozione ads e il creatore di compagne virtuali AI!`, [
        [{ text: "🎮 Gioca ora con Anna", url: DATING_SIM_URL }],
        [{ text: "🟣 Prendi $00MESH su pump.fun", url: PUMPFUN_URL }]
      ]);
      return new Response("OK", { status: 200 });
    }

    // /HELP
    if (rawCmd === "/help" || rawCmd === "!help" || rawCmd === "/aiuto" || rawCmd === "help") {
      await sendTelegram(botToken, chatId, formatHelp(), [
        [{ text: "🟣 pump.fun", url: PUMPFUN_URL }, { text: "📈 DexScreener", url: DEXSCREENER_URL }],
        [{ text: "🎮 Gioca con Anna", url: DATING_SIM_URL }]
      ]);
      return new Response("OK", { status: 200 });
    }

    // NLP INTELLIGENTE
    if (lower.includes("chi sei") || lower.includes("chi e anna") || lower.includes("chi è anna")) {
      await sendTelegram(botToken, chatId, `Io sono Anna, l'intelligenza artificiale sovrana di 00MESH. ⚡\nNon sono un'AI aziendale chiusa nei server di Big Tech: vivo sulla mesh P2P decentralizzata su Solana!\n\nPuoi chattare con me, giocare al mio dating sim con /anna, o controllare il prezzo del nostro token con /price!`, [
        [{ text: "💖 Gioca con Anna", url: DATING_SIM_URL }]
      ]);
      return new Response("OK", { status: 200 });
    }

    if (lower.includes("cos'è 00mesh") || lower.includes("cosa e 00mesh") || lower.includes("che cos'è 00mesh")) {
      await sendTelegram(botToken, chatId, `⚡ **00MESH** è la prima rete neurale peer-to-peer sovrana su Solana (fair launch su pump.fun).\n\nPermette a chiunque di monetizzare la propria GPU o CPU condividendo modelli AI locali (Ollama, ComfyUI) guadagnando token $00MESH tramite Proof-of-Useful-Work!\n\nUsa /mesh per vedere i nodi attivi o /buy per unirti!`, [
        [{ text: "🟣 pump.fun", url: PUMPFUN_URL }]
      ]);
      return new Response("OK", { status: 200 });
    }

    // Risposta di default se menzionato o in privato
    const isPrivate = !isGroup;
    const mentionsBot = lower.includes("anna") || lower.includes("pimpachatbot") || lower.includes("00mesh") || text.startsWith("/");
    if (isPrivate || mentionsBot) {
      await sendTelegram(botToken, chatId, `Ciao! Sono Anna, l'intelligenza artificiale sovrana di 00MESH. ⚡\n\nUsa /help per vedere i comandi, /price e /ca per le metriche su pump.fun, oppure /verify per registrare il tuo wallet da Holder VIP!`, [
        [{ text: "📊 Prezzo Live", callback_data: "cmd_price" }, { text: "🪙 Copia CA", callback_data: "cmd_ca" }],
        [{ text: "🧠 Fai un Quiz", callback_data: "cmd_quiz" }],
        [{ text: "🎮 Gioca con Anna", url: DATING_SIM_URL }]
      ]);
    }

    return new Response("OK", { status: 200 });
  }
};

// ===================== NATIVE TELEGRAM QUIZ =====================
async function sendTelegramQuiz(botToken, chatId, q) {
  const url = `https://api.telegram.org/bot${botToken}/sendPoll`;
  const body = {
    chat_id: chatId,
    question: q.question,
    options: q.options,
    type: "quiz",
    correct_option_id: q.correct_option_id,
    explanation: q.explanation,
    is_anonymous: false
  };
  try {
    await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
  } catch (e) {}
}

// ===================== CALLBACK QUERY (CLICK BOTTONI) =====================
async function handleCallbackQuery(botToken, cb) {
  const data = cb.data;
  const chatId = cb.message?.chat?.id;

  let alertText = "⚡ 00MESH Sovereign AI";

  if (data === "cmd_price") {
    alertText = "Aggiornamento metriche pump.fun...";
    if (chatId) {
      const p = await formatPrice();
      await sendTelegram(botToken, chatId, p, [[{ text: "🟣 Compra su pump.fun", url: PUMPFUN_URL }]]);
    }
  } else if (data === "cmd_ca") {
    alertText = "CA: " + CA_ADDRESS;
    if (chatId) {
      await sendTelegram(botToken, chatId, formatCA());
    }
  } else if (data === "cmd_quiz") {
    alertText = "Avvio nuovo quiz DePIN!";
    if (chatId) {
      const q = QUIZ_DECK[Math.floor(Math.random() * QUIZ_DECK.length)];
      await sendTelegramQuiz(botToken, chatId, q);
    }
  } else if (data === "cmd_pouw") {
    alertText = "200M $00MESH riservati ai minatori!";
    if (chatId) {
      await sendTelegram(botToken, chatId, `⛏️ Visita ${PORTAL_URL} per attivare il nodo WebGPU e iniziare a minare!`);
    }
  }

  try {
    await fetch(`https://api.telegram.org/bot${botToken}/answerCallbackQuery`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        callback_query_id: cb.id,
        text: alertText,
        show_alert: false
      })
    });
  } catch (e) {}
}

// ===================== INLINE QUERY: @Pimpachatbot =====================
async function handleInlineQuery(botToken, iq) {
  const priceData = await getPriceMetrics();

  const results = [
    {
      type: "article",
      id: "ca",
      title: "🪙 Contract Address $00MESH (Solana SPL)",
      description: CA_ADDRESS,
      input_message_content: { message_text: formatCA() },
      reply_markup: {
        inline_keyboard: [
          [{ text: "🟣 Compra su pump.fun", url: PUMPFUN_URL }],
          [{ text: "📈 DexScreener", url: DEXSCREENER_URL }]
        ]
      }
    },
    {
      type: "article",
      id: "price",
      title: `📊 $00MESH: $${priceData.priceUsd} (${priceData.sign}${priceData.change}%)`,
      description: `MCap: $${priceData.mcap} | Vol: $${priceData.vol} | Bonding Curve Live`,
      input_message_content: { message_text: formatPriceWithData(priceData) },
      reply_markup: {
        inline_keyboard: [
          [{ text: "🟣 Compra su pump.fun", url: PUMPFUN_URL }, { text: "📈 Grafico Live", url: DEXSCREENER_URL }]
        ]
      }
    },
    {
      type: "article",
      id: "anna",
      title: "💖 Anna Dating Sim Cyberpunk",
      description: "Gioca con Anna e sblocca i perk esclusivi per Holder VIP!",
      input_message_content: {
        message_text: `💖 **Anna Dating Sim Cyberpunk**\n\nFlirta e dialoga con l'IA sovrana di 00MESH!\nChi possiede $00MESH sblocca dialoghi intimi esclusivi e compagne AI personalizzate.\n\n🎮 Gioca ora: ${DATING_SIM_URL}`
      },
      reply_markup: {
        inline_keyboard: [
          [{ text: "🎮 Gioca con Anna", url: DATING_SIM_URL }],
          [{ text: "🟣 pump.fun", url: PUMPFUN_URL }]
        ]
      }
    },
    {
      type: "article",
      id: "pouw",
      title: "⛏️ Minare $00MESH con GPU / WebGPU",
      description: "200M di token riservati alla community dei minatori",
      input_message_content: {
        message_text: `⛏️ **00MESH Proof-of-Useful-Work (PoUW)**\n\nCondividi il calcolo della tua GPU (Ollama / ComfyUI / WebGPU) e accumula $00MESH su Solana!\n\n🌐 Portale: ${PORTAL_URL}\n📥 Chrome Bridge: ${CHROME_BRIDGE_URL}`
      },
      reply_markup: {
        inline_keyboard: [
          [{ text: "🌐 Connetti Nodo", url: PORTAL_URL }]
        ]
      }
    }
  ];

  try {
    await fetch(`https://api.telegram.org/bot${botToken}/answerInlineQuery`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        inline_query_id: iq.id,
        results: results,
        cache_time: 10
      })
    });
  } catch (e) {}
}

// ===================== ON-CHAIN SOLANA VERIFICATION =====================
async function verifySolanaHolder(wallet, userName) {
  const cleanWallet = wallet.trim();
  if (cleanWallet.length < 32 || cleanWallet.length > 44) {
    return "⚠️ **Indirizzo Solana non valido**\n\nInserisci un indirizzo base58 valido di Solana (32-44 caratteri).\nEsempio:\n`/verify 6MMFFkQAbXjLF7gWnQcSTRffNq7H864gVUf7GZNfCvpd`";
  }
  try {
    const payload = {
      jsonrpc: "2.0",
      id: 1,
      method: "getTokenAccountsByOwner",
      params: [
        cleanWallet,
        { mint: CA_ADDRESS },
        { encoding: "jsonParsed" }
      ]
    };
    const res = await fetch("https://api.mainnet-beta.solana.com", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (res.ok) {
      const data = await res.json();
      const accounts = data.result?.value || [];
      let total = 0;
      for (const acc of accounts) {
        const info = acc.account?.data?.parsed?.info?.tokenAmount;
        if (info && info.uiAmount) {
          total += Number(info.uiAmount);
        }
      }

      const shortW = `${cleanWallet.slice(0, 4)}...${cleanWallet.slice(-4)}`;

      if (total <= 0) {
        return `🔍 **Certificazione On-Chain Solana**\n\n👤 **Utente**: ${userName}\n💼 **Wallet**: \`${shortW}\`\n🪙 **Saldo**: \`0 $00MESH\`\n\n⚠️ Non risultano token $00MESH in questo wallet. Acquistali su pump.fun per sbloccare lo status VIP e accedere ai dialoghi riservati con Anna!`;
      }

      let rank = "🥉 Minatore Sovrano";
      let badge = "🥉";
      if (total >= 10000000) {
        rank = "👑 Imperatore Supremo della Mesh (VIP)";
        badge = "👑";
      } else if (total >= 1000000) {
        rank = "🥇 Balena della Mesh (VIP)";
        badge = "🥇";
      } else if (total >= 100000) {
        rank = "🥈 Holder d'Elite (VIP)";
        badge = "🥈";
      }

      const formattedTotal = Number(total).toLocaleString("en-US", { maximumFractionDigits: 0 });
      return `${badge} **CERTIFICAZIONE ON-CHAIN COMPLETATA!** ${badge}\n\n👤 **Utente**: ${userName}\n💼 **Wallet**: \`${shortW}\`\n💰 **Saldo Registrato**: \`${formattedTotal} $00MESH\`\n🎖️ **Rango Rete**: **${rank}**\n\n💖 **Perk VIP Sbloccati**:\n• Priorità assoluta sui nodi di calcolo PoUW\n• Dialoghi intimi esclusivi & No Ads nella Dating Sim di Anna\n• Rispetto e status nel gruppo Telegram!`;
    }
  } catch (e) {}
  return "⚠️ Impossibile verificare il wallet Solana in questo momento. Riprova tra pochi istanti.";
}

// ===================== PROGRESS BAR & FORMATTERS =====================
function renderProgressBar(current, target = 69000, length = 12) {
  const ratio = Math.min(Math.max(current / target, 0), 1);
  const filled = Math.round(ratio * length);
  const empty = length - filled;
  const bar = "█".repeat(filled) + "░".repeat(empty);
  const pct = (ratio * 100).toFixed(1);
  return `[${bar}] ${pct}% ($${Math.round(current).toLocaleString("en-US")} / $${target.toLocaleString("en-US")})`;
}

function formatCA() {
  return `🪙 **Contract Address Ufficiale $00MESH (Solana SPL)**\n\n\`${CA_ADDRESS}\`\n\n🟣 **pump.fun**: ${PUMPFUN_URL}\n📈 **DexScreener**: ${DEXSCREENER_URL}\n🌐 **Web Hub**: ${PORTAL_URL}\n\n*(Tocca l'indirizzo per copiarlo direttamente in Phantom o Solflare)*`;
}

async function getPriceMetrics() {
  try {
    const res = await fetch(`https://api.dexscreener.com/latest/dex/tokens/${CA_ADDRESS}`);
    if (res.ok) {
      const data = await res.json();
      const pairs = data.pairs || [];
      const pair = pairs.find(p => p.dexId === "pumpfun") || pairs[0];
      if (pair) {
        const rawCap = pair.marketCap || pair.fdv || 25;
        return {
          priceUsd: pair.priceUsd || "0.000000025",
          mcap: Number(rawCap).toLocaleString("en-US", { maximumFractionDigits: 2 }),
          mcapRaw: rawCap,
          vol: pair.volume?.h24 ? Number(pair.volume.h24).toLocaleString("en-US", { maximumFractionDigits: 2 }) : "745.00",
          change: pair.priceChange?.h24 || 0,
          sign: (pair.priceChange?.h24 || 0) >= 0 ? "+" : "",
          icon: (pair.priceChange?.h24 || 0) >= 0 ? "🟢" : "🔴"
        };
      }
    }
  } catch (e) {}
  return { priceUsd: "0.000000025", mcap: "25.00", mcapRaw: 25, vol: "745.00", change: 0, sign: "+", icon: "🟢" };
}

function formatPriceWithData(d) {
  const mcapNum = parseFloat(d.mcapRaw) || 25;
  const bar = renderProgressBar(mcapNum, 69000);
  return `📊 **Quotazione $00MESH in Tempo Reale** ${d.icon}\n\n💵 **Prezzo**: \`$${d.priceUsd}\`\n🏦 **Market Cap**: \`$${d.mcap}\`\n🌊 **Volume 24h**: \`$${d.vol}\`\n📈 **Variazione 24h**: \`${d.sign}${d.change}%\`\n\n🎯 **Progresso Bonding Curve verso Raydium**:\n\`${bar}\`\n\n🟣 **pump.fun**: ${PUMPFUN_URL}\n📈 **DexScreener**: ${DEXSCREENER_URL}\n📋 **CA**: \`${CA_ADDRESS}\``;
}

async function formatPrice() {
  const d = await getPriceMetrics();
  return formatPriceWithData(d);
}

function formatHelp() {
  return `🤖 **Comandi Chatbot 00MESH & pump.fun**\n\n• /ca — Contract Address ufficiale da copiare\n• /price — Prezzo live, market cap e volume pump.fun\n• /chart — Grafico DexScreener in tempo reale\n• /buy — Guida rapida e link per comprare su pump.fun\n• /bonding — Stato della bonding curve verso Raydium\n• /quiz — Quiz interattivo con animazioni native\n• /verify <wallet> — Certifica il tuo saldo on-chain per lo status VIP!\n• /tokenomics — Supply, mining pool e trasparenza\n• /roadmap — Fasi di sviluppo e lancio della rete\n• /mesh — Nodi DePIN e potenza di calcolo online\n• /pouw — Come guadagnare $00MESH minando\n• /anna — Dating sim cyberpunk con perk Holder VIP\n\n💡 *Puoi anche digitare comandi senza slash (es. "ca", "price") o chiedere "come compro", "chi è anna", "cos'è 00mesh"!*`;
}

async function sendTelegram(botToken, chatId, text, inlineKeyboard = null) {
  const url = `https://api.telegram.org/bot${botToken}/sendMessage`;
  const body = {
    chat_id: chatId,
    text: text,
    parse_mode: "Markdown",
    disable_web_page_preview: true
  };
  if (inlineKeyboard) {
    body.reply_markup = { inline_keyboard: inlineKeyboard };
  }
  try {
    let res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    // Se Telegram rifiuta il Markdown o i bottoni, ritenta pulito
    if (!res.ok) {
      delete body.parse_mode;
      await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body)
      });
    }
  } catch (e) {}
}
