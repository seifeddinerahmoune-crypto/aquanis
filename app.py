import express from "express";
import path from "path";
import { fileURLToPath } from "url";
import { createServer as createViteServer } from "vite";
import { GoogleGenAI } from "@google/genai";
import dotenv from "dotenv";

dotenv.config();

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = 3000;

app.use(express.json({ limit: "10mb" }));

// Lazy initialization of Gemini client
let genAI: GoogleGenAI | null = null;
function getGenAI(): GoogleGenAI | null {
  if (!genAI && process.env.GEMINI_API_KEY) {
    genAI = new GoogleGenAI({
      apiKey: process.env.GEMINI_API_KEY,
      httpOptions: {
        headers: {
          "User-Agent": "aistudio-build",
        },
      },
    });
  }
  return genAI;
}

// Hydraulics fallback knowledge engine for offline / unconfigured API keys
function getHydraulicsFallbackResponse(message: string, language: string = "en"): string {
  const lower = message.toLowerCase();
  
  if (lower.includes("v =") || lower.includes("q/a") || lower.includes("velocity") || lower.includes("débit") || lower.includes("vitesse") || lower.includes("سرعة")) {
    if (language === "fr") {
      return `### Équation de Continuité et Vitesse d'Écoulement

Pour un écoulement incompressible dans une conduite circulaire de diamètre $D$ et de section $A$ :

$$V = \\frac{Q}{A} = \\frac{Q}{\\frac{\\pi D^{2}}{4}} = \\frac{4Q}{\\pi D^{2}}$$

Où :
- $V$ : Vitesse moyenne d'écoulement ($m/s$)
- $Q$ : Débit volumique ($m^3/s$)
- $A$ : Aire de la section transversale ($m^2$), avec $A = \\frac{\\pi D^2}{4}$
- $D$ : Diamètre intérieur de la conduite ($m$)

**Application pratique :** Si vous doublez le diamètre $D$ pour un même débit $Q$, la vitesse est divisée par 4 car $V \\propto \\frac{1}{D^2}$.`;
    } else if (language === "ar") {
      return `### معادلة الاستمرارية وسرعة الجريان

للجريان غير القابل للانضغاط في أنبوب دائري ذي قطر $D$ ومساحة مقطع $A$:

$$V = \\frac{Q}{A} = \\frac{Q}{\\frac{\\pi D^{2}}{4}} = \\frac{4Q}{\\pi D^{2}}$$

حيث:
- $V$: متوسط سرعة الجريان ($m/s$)
- $Q$: معدل التدفق الحجمي ($m^3/s$)
- $A$: مساحة المقطع العرضي ($m^2$)، حيث $A = \\frac{\\pi D^2}{4}$
- $D$: القطر الداخلي للأنبوب ($m$)

**ملاحظة هيدروليكية:** إذا تضاعف قطر الأنبوب $D$ مع بقاء التدفق $Q$ ثابتاً، تنخفض السرعة بمقدار الربع لأن $V \\propto \\frac{1}{D^2}$.`;
    }
    return `### Pipe Flow Velocity & Continuity Equation

For steady, incompressible flow through a circular pipe of internal diameter $D$ and cross-sectional area $A$:

$$V = \\frac{Q}{A} = \\frac{Q}{\\frac{\\pi D^{2}}{4}} = \\frac{4Q}{\\pi D^{2}}$$

Where:
- $V$ : Mean fluid flow velocity ($m/s$ or $ft/s$)
- $Q$ : Volumetric flow rate ($m^3/s$ or $cfs$)
- $A$ : Pipe cross-sectional area ($m^2$ or $ft^2$), given by $A = \\frac{\\pi D^2}{4}$
- $D$ : Internal pipe diameter ($m$ or $ft$)

**Key Engineering Insights:**
1. **Inverse Square Law**: Velocity varies inversely with the square of the pipe diameter ($V \\propto 1/D^2$). Doubling pipe diameter reduces velocity to $25\\%$.
2. **Economic Sizing**: Standard water distribution networks typically target velocities between $1.0\\text{ m/s}$ and $2.5\\text{ m/s}$ to minimize both pumping friction losses and pipe installation capital costs.`;
  }

  if (lower.includes("bernoulli")) {
    return `### The Bernoulli Equation

For steady, incompressible, inviscid flow along a streamline:

$$P_1 + \\frac{1}{2} \\rho V_1^2 + \\rho g z_1 = P_2 + \\frac{1}{2} \\rho V_2^2 + \\rho g z_2$$

Divided by specific weight $\\gamma = \\rho g$, it is expressed in terms of **hydraulic heads** (meters of fluid column):

$$\\underbrace{\\frac{P_1}{\\gamma}}_{\\text{Pressure Head}} + \\underbrace{\\frac{V_1^2}{2g}}_{\\text{Velocity Head}} + \\underbrace{z_1}_{\\text{Elevation Head}} = \\frac{P_2}{\\gamma} + \\frac{V_2^2}{2g} + z_2 + h_L$$

Where $h_L$ represents total head loss (pipe friction + minor local losses).`;
  }

  if (lower.includes("darcy") || lower.includes("head loss") || lower.includes("weisbach") || lower.includes("perte de charge")) {
    return `### Darcy-Weisbach Equation for Head Loss

Frictional head loss $h_f$ in a pressurized pipe is governed by:

$$h_f = f \\cdot \\frac{L}{D} \\cdot \\frac{V^2}{2g}$$

Substituting the continuity velocity $V = \\frac{4Q}{\\pi D^2}$:

$$h_f = f \\cdot \\frac{L}{D} \\cdot \\frac{1}{2g}\\left(\\frac{4Q}{\\pi D^2}\\right)^2 = \\frac{8 f L Q^2}{\\pi^2 g D^5}$$

Notice that frictional head loss scales inversely with $D^5$! Sizing up a pipe slightly yields massive reductions in pumping energy head.`;
  }

  if (lower.includes("reynolds")) {
    return `### Reynolds Number ($Re$) & Flow Regimes

The dimensionless Reynolds number quantifies the ratio of inertial forces to viscous forces:

$$Re = \\frac{\\rho V D}{\\mu} = \\frac{V D}{\\nu}$$

Where:
- $\\rho$ : Fluid density ($kg/m^3$, $\\approx 1000\\text{ kg/m}^3$ for water at $20^\\circ\\text{C}$)
- $V$ : Mean flow velocity ($m/s$)
- $D$ : Internal pipe diameter ($m$)
- $\\mu$ : Dynamic viscosity ($Pa\\cdot s$ or $N\\cdot s/m^2$)
- $\\nu = \\mu / \\rho$ : Kinematic viscosity ($m^2/s$, $\\approx 1.004 \\times 10^{-6}\\text{ m}^2/s$ for water at $20^\\circ\\text{C}$)

**Flow Regimes in Closed Conduits:**
- **Laminar Flow**: $Re < 2300$ (Friction factor $f = \\frac{64}{Re}$)
- **Transitional Zone**: $2300 \\le Re \\le 4000$ (Unstable)
- **Turbulent Flow**: $Re > 4000$ (Governed by Colebrook-White equation or Moody chart)`;
  }

  if (lower.includes("water hammer") || lower.includes("coup de bélier") || lower.includes("مطرقة")) {
    return `### Water Hammer (Joukowsky Surge Pressure)

When a valve closes rapidly in time $t_c < \\frac{2L}{a}$, a pressure wave propagates through the fluid. The maximum transient pressure rise $\\Delta P$ is given by the **Joukowsky Equation**:

$$\\Delta P = \\rho \\cdot a \\cdot \\Delta V$$

In terms of pressure head rise $\\Delta H$:

$$\\Delta H = \\frac{a \\cdot \\Delta V}{g}$$

Where:
- $a$ : Pressure wave propagation speed (celerity), typically $900 - 1200\\text{ m/s}$ in steel/ductile iron pipes
- $\\Delta V$ : Rapid reduction in flow velocity ($m/s$)
- $g$ : Acceleration due to gravity ($9.81\\text{ m/s}^2$)

**Mitigation Measures:**
- Slow-closing automated valves ($t > 2L/a$)
- Surge tanks and air relief chambers
- Water hammer arrestors and pressure relief valves`;
  }

  return `### Aquanis Hydraulics Assistant

Hydraulic calculation and fluid mechanics overview for your query:

Continuity equation across pipe cross-sections:
$$Q = A_1 V_1 = A_2 V_2$$

For circular pipes with diameter $D$:
$$V = \\frac{Q}{A} = \\frac{4Q}{\\pi D^2}$$

Total energy grade line (EGL) with head losses:
$$H_1 = H_2 + h_f + h_m$$

Where $h_f = f \\frac{L}{D} \\frac{V^2}{2g}$ and minor losses $h_m = \\sum K \\frac{V^2}{2g}$.

Feel free to specify your pipe parameters ($Q$, $D$, fluid properties, roughness) or ask about pumps, open channel flow, or transient surges!`;
}

// API Health Check
app.get("/api/health", (_req, res) => {
  res.json({
    status: "ok",
    hasApiKey: Boolean(process.env.GEMINI_API_KEY),
  });
});

// API Route for Hydraulics Chat Assistant
app.post("/api/chat", async (req, res) => {
  try {
    const { message, language = "en" } = req.body;

    if (!message || typeof message !== "string") {
      res.status(400).json({ error: "Message is required" });
      return;
    }

    const ai = getGenAI();

    if (!ai) {
      const fallbackText = getHydraulicsFallbackResponse(message, language);
      res.json({
        reply: fallbackText,
        source: "aquanis_hydraulics_engine",
      });
      return;
    }

    const systemInstruction = `You are Aquanis, an elite scientific and engineering AI assistant specialized in fluid mechanics, hydraulics, hydrology, and pipe network engineering.

CRITICAL MATHEMATICAL FORMATTING RULES:
1. Always format all mathematical formulas, fractions, derivatives, and equations using clean, standard LaTeX syntax.
2. For standalone display equations, ALWAYS enclose them in double dollar signs: $$ ... $$
   Example:
   $$V = \\frac{Q}{A} = \\frac{Q}{\\frac{\\pi D^{2}}{4}} = \\frac{4Q}{\\pi D^{2}}$$
3. For inline variables and math, ALWAYS enclose them in single dollar signs: $V$, $Q$, $D$, $\\rho$, $\\mu$.
4. NEVER use brackets like ([ ... ]) or [ ... ] or \\( ... \\) or \\[ ... \\] for equations without dollar signs.
5. Provide step-by-step mathematical derivations, clearly defining every physical variable, its SI unit, and practical hydraulic rules of thumb.
6. Language: If the user asks in French, answer in French. If in Arabic, answer in Arabic. If in English, answer in English.`;

    const promptWithLang = `[User Language: ${language}]\n\nUser Question: ${message}`;

    const response = await ai.models.generateContent({
      model: "gemini-3.8-flash",
      contents: promptWithLang,
      config: {
        systemInstruction,
        temperature: 0.2,
      },
    });

    const reply = response.text || getHydraulicsFallbackResponse(message, language);
    res.json({
      reply,
      source: "gemini",
    });
  } catch (error: any) {
    console.error("Gemini API error in /api/chat:", error);
    const fallbackText = getHydraulicsFallbackResponse(
      req.body?.message || "",
      req.body?.language || "en"
    );
    res.json({
      reply: fallbackText,
      source: "fallback_recovery",
      error: error?.message,
    });
  }
});

async function startServer() {
  if (process.env.NODE_ENV !== "production") {
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: "spa",
    });
    app.use(vite.middlewares);
  } else {
    const distPath = path.join(process.cwd(), "dist");
    app.use(express.static(distPath));
    app.get("*", (_req, res) => {
      res.sendFile(path.join(distPath, "index.html"));
    });
  }

  app.listen(PORT, "0.0.0.0", () => {
    console.log(`Aquanis hydraulics server running at http://0.0.0.0:${PORT}`);
  });
}

startServer();
