#!/usr/bin/env python3
"""Build publication-grade, multi-page PDF Field Guides blending rich poetic prose with deep biophysics & Fullscript links.

Restores the profound, luminous tone ("The skin is not where you end. It is where you exchange.")
across 5-to-6 page field manuals for all 6 Biophysics Frameworks:
1. Living Waters (Fluid & Transport)
2. Inner Garden (Gut Ecology)
3. Cell Shedding (Senescence & Renewal)
4. Higher Flame (Metabolism & Respiration)
5. Luminous Mind (Cognition & Neural Coherence)
6. Dark Mirror (Mineral & Bio-clearing)
"""

import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle, PageBreak, KeepTogether
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

DEST_DIR = Path(__file__).resolve().parent.parent / "public" / "downloads" / "field-guides"
DEST_DIR.mkdir(parents=True, exist_ok=True)

class NumberedCanvas(canvas.Canvas):
    """Canvas for multi-page documents adding running headers and footers with Page X of Y."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#6B7280"))
        
        # Running Header (Pages 2+)
        if self._pageNumber > 1:
            self.drawString(0.55 * inch, 10.45 * inch, "SPIRAL OF CELLULAR LIGHT — CERTIFIED REGENERATIVE HEALTH PROGRAM")
            self.drawRightString(8.5 * inch - 0.55 * inch, 10.45 * inch, "AGEWELL BRIEF FIELD GUIDE")
            self.setStrokeColor(colors.HexColor("#D97706"))
            self.setLineWidth(0.5)
            self.line(0.55 * inch, 10.38 * inch, 8.5 * inch - 0.55 * inch, 10.38 * inch)

        # Running Footer (All Pages)
        self.setStrokeColor(colors.HexColor("#E2DDD3"))
        self.setLineWidth(0.5)
        self.line(0.55 * inch, 0.65 * inch, 8.5 * inch - 0.55 * inch, 0.65 * inch)
        
        self.drawString(0.55 * inch, 0.48 * inch, "Prepared by Spiral of Cellular Light · agewellbrief.com")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(8.5 * inch - 0.55 * inch, 0.48 * inch, page_text)
        self.restoreState()


FIELD_GUIDES = [
    {
        "slug": "living-waters-field-guide.pdf",
        "title": "Living Waters Field Guide",
        "subtitle": "Fluid Dynamics, Interfacial EZ Water & Vascular Transport Kinetics",
        "emoji": "🌊",
        "domain": "Fluid & Micro-Circulation",
        "fullscript_url": "https://ca.fullscript.com/s/spiraloflight/shop/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ0NA==",
        "fullscript_plan_name": "Living Waters Practitioner Protocol",
        "summary": "Water inside human tissue is not mere bulk fluid—it forms structured Exclusion Zone (EZ) water (H3O2) along hydrophilic cell membranes, driving vascular micro-circulation and cellular clearing.",
        "introduction": (
            "Most health protocols jump straight to interventions—herbs, detoxes, senolytics, or fasting. "
            "They ask the body to release stored heavy metals, metabolic debris, and environmental toxins without first ensuring "
            "that the rivers of transport are open to receive them. This creates a catch-22 at its most visceral: "
            "toxins are mobilized into circulation but cannot exit, recirculating through brain and tissue, causing headaches, brain fog, and fatigue.<br/><br/>"
            "Water inside human tissue is not passive background fluid. Along hydrophilic cell membranes, liquid water reorganizes into "
            "crystalline Exclusion Zone (EZ) water (H3O2)—a dense phase carrying negative electric potential that drives micro-vascular flow "
            "and powers cellular clearance without relying solely on cardiac pumping."
        ),
        "two_phases": [
            ("Phase I: Transformation & Activation", "Cytochrome P450 enzymes in liver cells transform fat-soluble toxins into active intermediate metabolites. These intermediates are often more reactive than the original toxin and require immediate Phase II processing."),
            ("Phase II: Conjugation & Neutralization", "Transferase enzymes attach hydrophilic molecules (glutathione, glycine, glucuronic acid) to intermediate toxins, neutralizing their toxicity and making them water-soluble for excretion.")
        ],
        "three_exits": [
            ("1. Kidneys — Water", "The kidneys filter water-soluble conjugated toxins from the blood and release them through urine. Hydrate 2–3 litres of filtered water daily. Warm water with lemon on waking opens the renal pathway. The kidneys cannot flush what there is no river to move."),
            ("2. Gut — Earth", "Conjugated toxins riding bile enter the duodenum and travel the length of the intestines. If the bowels stall, toxins in bile are reabsorbed across the gut wall into systemic blood. Daily bowel motility is non-negotiable during any clearing protocol."),
            ("3. Skin — Air", "The skin is your largest elimination organ—two square metres of living, breathing membrane. Sweat carries traces of what the liver transformed and blood delivered. 20 minutes of daily sweating (exercise, sauna, hot bath) ensures the skin actively participates in clearing. The skin is not where you end. It is where you exchange.")
        ],
        "protocol_table": [
            ["Timing", "Supplement & Form", "Dose", "Target Mechanism & Purpose"],
            ["Morning (with food)", "Vitamin D3 + K2 Matrix", "5,000 IU D3 / 100mcg K2", "Directs calcium from vascular walls to bone matrix"],
            ["Morning (with food)", "Vitamin C (L-Ascorbic Acid)", "1,000 mg", "Primary aqueous phase antioxidant; supports Phase I liver co-factors"],
            ["Morning (with food)", "N-Acetyl Cysteine (NAC)", "1,000 mg", "Direct precursor to intracellular glutathione; neutralizes Phase I intermediates"],
            ["Throughout Day", "Filtered Ionic Electrolyte Water", "2–3 Litres", "Expands interfacial EZ water layers and maintains capillary fluid flow"],
            ["Evening (with dinner)", "Magnesium Citrate / Malate", "350–1,000 mg", "Supports Phase II liver enzymes and ensures non-negotiable daily bowel motility"],
            ["Evening (every 3 days)", "Alpha-Lipoic Acid (ALA)", "300–600 mg", "Mobilizes stored heavy metals from brain tissue during nocturnal sleep clearance"],
            ["Before Bed (Optional)", "Sodium Bicarbonate in Water", "½ tsp (2hr after meal)", "Alkalinizes urine to optimize renal filtration and uric acid excretion"]
        ],
        "timeline": [
            ("Week 1 — Foundation", "Bowel frequency increases as magnesium takes effect. Increased hydration supports renal clearance. Energy levels remain steady as fluid pathways open."),
            ("Week 2 — Glutathione Synthesis", "Intracellular glutathione levels build from NAC. Phase II conjugation expands. Mild detox sensations on ALA days signify nightly brain metal clearing."),
            ("Week 3–4 — Systemic Coherence", "Transport systems operate at a elevated baseline. Sleep quality deepens as glymphatic fluid flow operates without toxic recirculation.")
        ],
        "bigger_picture": (
            "The Living Waters protocol is the permanent foundation beneath a larger regenerative framework—six interconnected "
            "Spirals that address the body's major systems in a specific, deliberate sequence: Living Waters (Transport), Inner Garden (Gut), "
            "Cell Shedding (Senescence), Higher Flame (Metabolism), Luminous Mind (Brain), and Dark Mirror (Mineral Clearing).<br/><br/>"
            "Each protocol builds on the ones before it. Transport clearing ensures that every subsequent intervention can do its work "
            "safely. The protocols are designed to be repeated at the equinoxes—twice a year—following natural rhythms of clearing and renewal."
        )
    },
    {
        "slug": "inner-garden-field-guide.pdf",
        "title": "Inner Garden Field Guide",
        "subtitle": "Gut Microbiome Ecology, SCFA Signaling & Mucosal Barrier Integrity",
        "emoji": "🌱",
        "domain": "Gut Microbiome Ecology",
        "fullscript_url": "https://ca.fullscript.com/s/spiraloflight/shop/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ0OQ==",
        "fullscript_plan_name": "Inner Garden Practitioner Protocol",
        "summary": "The human gut is a living microbial rainforest where short-chain fatty acids (butyrate, acetate, propionate) communicate with the vagus nerve, regulate mucosal integrity, and coordinate systemic metabolism.",
        "introduction": (
            "We tend to think of digestion as a mechanical disassembly line. Biologically, the gut is an internal garden—a dense, "
            "interconnected ecosystem of over 100 trillion organisms whose metabolic output directly dictates human systemic immunity, "
            "neuro-inflammation, and mood.<br/><br/>"
            "The gut mucosal barrier is a delicate single-cell architecture separating systemic circulation from lumenal antigens. "
            "When tight junction proteins break down, bacterial lipopolysaccharides (LPS) breach the bloodstream, igniting systemic inflammation. "
            "Restoring this barrier requires more than isolated probiotics—it demands feeding keystone species that produce protective short-chain fatty acids."
        ),
        "two_phases": [
            ("Phase I: Epithelial Barrier Fortification", "Providing specialized amino acids and mucosal nutrients to seal tight junctions (zonulin, occludin) and restore the protective mucin-2 (MUC2) gel layer."),
            ("Phase II: Keystone Microbial Diversification", "Introducing fermentable prebiotic fibers and polyphenols to selectively nourish keystone taxa like Akkermansia muciniphila and Faecalibacterium prausnitzii.")
        ],
        "three_exits": [
            ("1. Mucosal Epithelium — Soil", "The gut lining requires constant fuel. Colonocyte epithelial cells derive 70% of their energy directly from lumenal butyrate. Without adequate butyrate, the intestinal lining starves, thinning the protective barrier."),
            ("2. Vagus Nerve — Electric Axis", "80% of vagus nerve fibers send sensory information from the gut up to the brain stem. Microbial neurotransmitters (GABA, serotonin, dopamine) modulate mood and neuro-inflammation via this electrical superhighway."),
            ("3. Intestinal Motility — Wave", "The Migrating Motor Complex (MMC) sweeps the small intestine clean during fasting windows. If motility stalls, bacteria migrate upward, causing SIBO and fermentation distress. Rhythm is essential to microbial ecology.")
        ],
        "protocol_table": [
            ["Timing", "Supplement & Form", "Dose", "Target Mechanism & Purpose"],
            ["Morning (Fasted)", "Soil-Based Organism (SBO) Probiotic", "5–10 Billion CFU", "Survives gastric stomach acid to seed diverse spore colonies in lower gut"],
            ["30 min Before Meals", "L-Glutamine Powder", "5,000 mg", "Primary metabolic substrate for enterocyte mucosal repair and tight junction restoration"],
            ["30 min Before Meals", "Zinc Carnosine", "37.5 mg", "Stabilizes small intestine mucosal lining and accelerates epithelial wound healing"],
            ["With Meals", "Polyphenol & Acacia Prebiotic Fiber", "5 g", "Selectively feeds Akkermansia muciniphila to thicken protective intestinal mucus layer"],
            ["Evening (Bedtime)", "Sodium Butyrate (Delayed Release)", "600–1,200 mg", "Direct SCFA colonocyte fuel; downregulates nuclear factor kappa B (NF-kB) neuro-inflammation"]
        ],
        "timeline": [
            ("Week 1 — Mucosal Calm", "Intestinal bloating decreases as L-Glutamine seals hyper-permeable mucosal junctions. Stool consistency stabilizes."),
            ("Week 2 — Microbial Expansion", "Prebiotic polyphenols feed beneficial keystone species. Short-chain fatty acid levels rise, dampening systemic inflammation."),
            ("Week 3–4 — Gut-Brain Resonation", "Vagal tone improves. Neurotransmitter precursors synthesized by gut microbes enhance mental clarity, energy, and sleep depth.")
        ],
        "bigger_picture": (
            "The Inner Garden protocol restores the biological soil. Once transport pathways are open and mucosal integrity is sealed, "
            "the body can absorb nutrients efficiently, clear senescent cells safely, and sustain metabolic flexibility without systemic inflammatory interference."
        )
    },
    {
        "slug": "cell-shedding-field-guide.pdf",
        "title": "Cell Shedding Field Guide",
        "subtitle": "Targeted Senolytic Clearing, Autophagy Activation & SASP Reduction",
        "emoji": "🍃",
        "domain": "Senescence & Cellular Renewal",
        "fullscript_url": "https://ca.fullscript.com/s/spiraloflight/shop/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ1MA==",
        "fullscript_plan_name": "Cell Shedding Practitioner Protocol",
        "summary": "Senescent cells are non-dividing 'zombie' cells that linger in tissue, secreting pro-inflammatory SASP cytokines that degrade surrounding cellular architecture. Periodic senolytic clearing restores youthful tissue dynamics.",
        "introduction": (
            "As cells age or undergo persistent DNA damage, they reach a biological crossroad: undergo apoptosis (programmed cell death) "
            "or enter a state of permanent arrest called senescence. Senescent cells refuse to die, lingering like 'zombies' in organ tissue.<br/><br/>"
            "While initial senescence prevents cancer, the long-term accumulation of senescent cells degrades healthy tissue. They secrete a toxic "
            "cocktail of inflammatory cytokines, chemokines, and tissue-destroying enzymes known as the Senescence-Associated Secretory Phenotype (SASP). "
            "Targeted senolytic clearing acts like seasonal pruning in an orchard, removing lingering zombie cells so stem cells can regenerate youthful tissue."
        ),
        "two_phases": [
            ("Phase I: Intermittent Senolytic Clearing ('Hit-and-Run')", "Senescent cells depend on specialized Anti-Apoptotic Pathways (SCAPs) to survive. Administering targeted plant flavonoids (Fisetin, Quercetin) in 2-day monthly pulses temporarily disables SCAPs, inducing apoptosis specifically in senescent cells."),
            ("Phase II: Autophagy Activation & Lysosomal Recycling", "Activating cellular self-cleaning (autophagy) between senolytic pulses ensures damaged organelle fragments and misfolded proteins are degraded and recycled into fresh amino acids.")
        ],
        "three_exits": [
            ("1. Macrophage Phagocytosis — Clearing", "Once a senescent cell undergoes senolytic-induced apoptosis, local tissue macrophages engulf and digest the cellular debris. Open transport pathways prevent inflammatory buildup."),
            ("2. Lysosomal Autophagy — Recycling", "Mitochondria and proteins inside healthy cells undergo constant autophagy. Spermidine and intermittent fasting stimulate lysosomal enzymes to digest degraded sub-cellular structures."),
            ("3. SASP Suppression — Quenching", "In between senolytic clearing pulses, botanical SASP dampeners (Curcumin, Boswellia, EGCG) suppress inflammatory cytokine release from remaining senescent cell populations.")
        ],
        "protocol_table": [
            ["Timing", "Supplement & Form", "Dose", "Target Mechanism & Purpose"],
            ["Pulse Days (Day 1 & 2)", "Liposomal Fisetin", "500–1,000 mg", "High-potency senolytic flavonoid; selectively induces apoptosis in senescent cells"],
            ["Pulse Days (Day 1 & 2)", "Liposomal Quercetin", "500 mg", "Disrupts BCL-2/BCL-XL senescent cell anti-apoptotic survival pathways"],
            ["Daily Maintenance", "Spermidine (Trihydrochloride)", "5–10 mg", "Triggers lysosomal autophagy and mitophagy, recycling misfolded cellular proteins"],
            ["Daily Maintenance", "Curcumin Phytosome & Boswellia", "500 mg", "Potent SASP dampener; blocks NF-kB and downregulates pro-inflammatory cytokines"],
            ["Post-Pulse Maintenance", "Resveratrol & Pterostilbene", "250 mg", "Activates SIRT1 sirtuin pathways, stimulating progenitor stem cell tissue renewal"]
        ],
        "timeline": [
            ("Pulse (Days 1–2)", "Senolytic flavonoids transiently disable zombie cell SCAP survival networks, triggering selective apoptosis in senescent cell populations."),
            ("Clearing (Days 3–7)", "Macrophages clear apoptotic senescent cell debris. SASP dampeners suppress inflammatory cytokine spikes. Mild transient fatigue may occur."),
            ("Renewal (Days 8–30)", "Tissue micro-environment rejuvenates. Progenitor stem cells expand, regenerating fresh, functional cell lines across targeted organs.")
        ],
        "bigger_picture": (
            "Cell Shedding is seasonal pruning. By clearing senescent cells in deliberate monthly or quarterly pulses, the body frees "
            "up vital energetic resources, reduces systemic inflammatory SASP burden, and allows fresh tissue renewal."
        )
    },
    {
        "slug": "higher-flame-field-guide.pdf",
        "title": "Higher Flame Field Guide",
        "subtitle": "Metabolic Flexibility, Mitochondrial Respiration Voltage & Fuel Switching",
        "emoji": "🔥",
        "domain": "Metabolic Resilience & Mitochondria",
        "fullscript_url": "https://ca.fullscript.com/s/spiraloflight/shop/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ0NQ==",
        "fullscript_plan_name": "Higher Flame Practitioner Protocol",
        "summary": "Metabolic health is defined by metabolic flexibility—the capacity to seamlessly transition between burning glucose and burning fatty acids based on fuel availability. High mitochondrial voltage (ΔΨm) fuels human vitality.",
        "introduction": (
            "Metabolism is not merely calories burned versus calories consumed. It is an intricate biophysical combustion process occurring "
            "inside thousands of mitochondria in every human cell. Mitochondria generate over 90% of cellular ATP energy by maintaining a high "
            "electrical voltage gradient (-140mV to -180mV) across their inner membranes.<br/><br/>"
            "Modern metabolic rigidity occurs when continuous nutrient oversupply overloads the mitochondrial electron transport chain. "
            "Re-igniting the Higher Flame means restoring the cell's capacity to burn glucose post-meal and rapidly switch to burning fats and ketones "
            "during fasting, exercise, and sleep."
        ),
        "two_phases": [
            ("Phase I: AMPK Activation & Insulin Sensitization", "Activating AMP-activated protein kinase (AMPK)—the master cellular energy sensor—signals the cell to translocate GLUT4 glucose transporters and consume circulating blood sugar without requiring excessive insulin."),
            ("Phase II: Mitochondrial Biogenesis & Substrate Switching", "Sirtuin activation (SIRT1, SIRT3) stimulates PGC-1α to build fresh, high-voltage mitochondria capable of efficient beta-oxidation of fatty acids.")
        ],
        "three_exits": [
            ("1. Mitochondrial Membrane Voltage (ΔΨm) — Spark", "The inner mitochondrial membrane acts as a microscopic capacitor. Maintaining cardiolipin lipid integrity and electron transport chain complexes preserves high ATP output without ROS leakage."),
            ("2. Carnitine Shuttle — Fuel Pipeline", "Long-chain fatty acids cannot cross inner mitochondrial membranes without acetyl-L-carnitine chaperones. Carnitine shuttle support unlocks deep tissue fat burning during fasting windows."),
            ("3. Non-Shivering Thermogenesis — Heat", "Cold exposure and uncoupling proteins (UCP1) dissipate excess metabolic fuel safely as heat in brown adipose tissue (BAT), resetting metabolic sensitivity.")
        ],
        "protocol_table": [
            ["Timing", "Supplement & Form", "Dose", "Target Mechanism & Purpose"],
            ["30 min Before Meals", "Berberine HCl (Phytosome)", "500 mg", "Potent AMPK activator; enhances insulin sensitivity and lowers postprandial blood glucose"],
            ["Morning (Fasted)", "CoQ10 (Ubiquinol) + PQQ", "200mg / 20mg", "Protects mitochondrial inner membrane cardiolipin and stimulates mitochondrial biogenesis"],
            ["Mid-Day", "Nicotinamide Riboside (NR) / NMN", "300 mg", "Elevates NAD+ substrate levels required for SIRT1/SIRT3 sirtuin mitochondrial enzyme activation"],
            ["Evening (with dinner)", "Alpha-Lipoic Acid (R-ALA)", "300 mg", "Universal antioxidant; recycles Vitamin C/E and enhances mitochondrial pyruvate dehydrogenase"],
            ["Bedtime", "Acetyl-L-Carnitine (ALCAR)", "1,000 mg", "Shuttles long-chain fatty acids into mitochondria for nocturnal beta-oxidation and ketone generation"]
        ],
        "timeline": [
            ("Week 1 — Fuel Sensitivity", "Post-meal blood glucose spikes flatten as AMPK activation enhances muscle glucose uptake. Afternoon energy slumps dissipate."),
            ("Week 2 — Fat Adaptation", "Carnitine shuttle upregulation enables smooth fuel switching during fasting windows. Hunger signals normalize as ketones rise."),
            ("Week 3–4 — Mitochondrial Density", "Sirtuin-mediated PGC-1α expression expands mitochondrial density. Physical stamina, thermal tolerance, and mental focus elevate.")
        ],
        "bigger_picture": (
            "The Higher Flame transforms how your cells turn light and food into life. Restoring mitochondrial respiration voltage "
            "supplies the bioenergetic power needed for deep tissue healing, cognitive clarity, and long-term vitality."
        )
    },
    {
        "slug": "luminous-mind-field-guide.pdf",
        "title": "Luminous Mind Field Guide",
        "subtitle": "Glymphatic Sleep Clearance, Neuro-Plasticity & Biophotonic Brain Coherence",
        "emoji": "⚡",
        "domain": "Cognitive & Neural Coherence",
        "fullscript_url": "https://ca.fullscript.com/s/spiraloflight/shop/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ0OA==",
        "fullscript_plan_name": "Luminous Mind Practitioner Protocol",
        "summary": "Brain health requires deep slow-wave sleep, during which Astrocyte-mediated glymphatic channels expand by 60% to flush neurotoxic metabolic waste (amyloid beta, tau) into lymphatic circulation.",
        "introduction": (
            "The human brain consumes 20% of total metabolic energy despite comprising only 2% of body mass. This intense metabolic activity "
            "generates significant neurochemical waste. Because the brain lacks traditional lymphatic vessels, waste clearance relies almost "
            "exclusively on the Glymphatic System—a specialized glial-vascular channel network active during deep slow-wave NREM sleep.<br/><br/>"
            "During deep Delta sleep, cortical brain cells shrink by 60%, allowing cerebrospinal fluid (CSF) to wash rapidly through neural tissue. "
            "Supporting glymphatic flow alongside Brain-Derived Neurotrophic Factor (BDNF) fosters neuro-plasticity, memory consolidation, and long-term neural coherence."
        ),
        "two_phases": [
            ("Phase I: Daytime Neuro-Plasticity & BDNF Induction", "Stimulating Brain-Derived Neurotrophic Factor (BDNF) and nerve growth factor (NGF) during waking hours enhances synaptic spine formation and cognitive resilience."),
            ("Phase II: Nocturnal Glymphatic Flush & Delta Coherence", "Optimizing Astrocyte Aquaporin-4 (AQP4) water channels during deep sleep accelerates the flushing of amyloid, tau, and metabolic waste into cervical lymphatics.")
        ],
        "three_exits": [
            ("1. Astrocyte AQP4 Channels — Current", "Aquaporin-4 water channels concentrated on astrocyte endfeet direct cerebrospinal fluid through brain parenchyma, sweeping metabolic debris out of cortical tissue."),
            ("2. Cervical Lymph Nodes — Drain", "Glymphatic fluid laden with neural waste drains through cribriform plate lymphatics down into deep cervical lymph nodes in the neck. Neck mobility supports drainage."),
            ("3. Subcellular Melatonin — Shield", "While pineal melatonin coordinates circadian sleep rhythms, brain mitochondria synthesize local intracellular melatonin to quench neural oxidative stress during high metabolic activity.")
        ],
        "protocol_table": [
            ["Timing", "Supplement & Form", "Dose", "Target Mechanism & Purpose"],
            ["Morning", "Organic Lion's Mane (Hericium erinaceus)", "1,000 mg", "Stimulates Nerve Growth Factor (NGF) and BDNF, promoting hippocampal neurogenesis"],
            ["Morning", "Bacopa Monnieri (50% Bacosides)", "300 mg", "Enhances synaptic neurotransmission speed, memory recall, and cholinergic signalling"],
            ["Mid-Day", "Phosphatidylserine (PS)", "200 mg", "Restores neuronal cell membrane fluidity and blunts excessive cortisol stress response"],
            ["60 min Before Bed", "Magnesium L-Threonate", "1,450 mg (2,000 mg)", "Uniquely crosses blood-brain barrier; density-enhances synaptic density and deep NREM sleep"],
            ["Bedtime", "Apigenin + Sublingual Melatonin", "50mg / 300mcg", "Calms excitatory glutamate signaling, activates GABA-A receptors, and triggers glymphatic flush"]
        ],
        "timeline": [
            ("Week 1 — Deep Delta Sleep", "Magnesium L-Threonate and Apigenin deepen slow-wave NREM sleep. Morning mental grogginess dissipates as glymphatic clearance activates."),
            ("Week 2 — Synaptic Speed", "Bacopa and Phosphatidylserine enhance focus, verbal recall, and emotional calm under cognitive stress."),
            ("Week 3–4 — Neural Coherence", "BDNF induction via Lion's Mane accelerates neuro-plasticity. Long-term memory consolidation and mental stamina optimize.")
        ],
        "bigger_picture": (
            "The Luminous Mind protocol treats the brain not as an isolated computer, but as a living biophotonic organ that thrives on "
            "rhythmic clearing, deep sleep, and neuro-trophic nourishment."
        )
    },
    {
        "slug": "dark-mirror-field-guide.pdf",
        "title": "Dark Mirror Field Guide",
        "subtitle": "Mineral Balance, Heavy Metal Chelation & Deep Tissue Bio-Clearing",
        "emoji": "🪞",
        "domain": "Mineral Balance & Bio-Clearing",
        "fullscript_url": "https://ca.fullscript.com/s/spiraloflight/shop/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ1Nw==",
        "fullscript_plan_name": "Dark Mirror Practitioner Protocol",
        "summary": "Heavy metals and bio-unavailable minerals bind to cellular enzymes, suppressing bioenergetic voltage. Systematic mineral replacement coupled with clinical-grade natural chelators restores enzyme kinetics and cellular vitality.",
        "introduction": (
            "Over decades, toxic heavy metals (lead, mercury, cadmium, aluminum) and halogen compounds (fluorine, chlorine, bromine) "
            "accumulate in deep connective tissue, bone matrix, and brain tissue. Because heavy metals share atomic radii with essential minerals, "
            "they displace vital ionic co-factors (zinc, copper, magnesium, selenium) from active enzyme binding pockets.<br/><br/>"
            "The Dark Mirror represents this hidden toxic burden. Clearing deep tissue metals requires more than aggressive chelation—it demands "
            "supplying abundant bio-available ionic minerals to displace toxic elements while providing intestinal binders to capture mobilized metals before re-absorption."
        ),
        "two_phases": [
            ("Phase I: Competitive Mineral Displacement", "Flooding systemic circulation with bio-available ionic trace minerals (fulvic/humic minerals, zinc, copper sebacate) displaces heavy metals from active enzyme sulfhydryl (-SH) binding sites."),
            ("Phase II: Intestinal Binding & Enterohepatic Interception", "Once mobilized metals are secreted via bile into the duodenum, specialized natural binders (modified citrus pectin, zeolite) intercept and bind metals, preventing re-absorption across gut walls.")
        ],
        "three_exits": [
            ("1. Biliary Cascade — Liver to Gut", "Hepatocytes conjugate heavy metals to glutathione and secrete them into bile. Flowing bile is essential to prevent hepatic toxic congestion."),
            ("2. Intestinal Binders — Soil Trap", "Modified Citrus Pectin (MCP) and Clinoptilolite Zeolite bind circulating heavy metals in the intestinal lumen like a molecular magnet, guaranteeing safe fecal excretion."),
            ("3. Metallothionein Induction — Shield", "Intracellular metallothionein proteins bind heavy metals safely inside cells, neutralizing their free radical toxicity until excretion pathways clear them.")
        ],
        "protocol_table": [
            ["Timing", "Supplement & Form", "Dose", "Target Mechanism & Purpose"],
            ["Morning (Fasted)", "Fulvic & Humic Ionic Mineral Complex", "1 mL in water", "Delivers 70+ bio-available ionic trace minerals to displace toxic heavy metals from enzymes"],
            ["Mid-Day (Between Meals)", "Modified Citrus Pectin (PectaSol-C)", "5,000 mg", "Systemic low-molecular-weight pectin; binds circulating lead, mercury, and cadmium in blood/gut"],
            ["Mid-Day (Between Meals)", "Clinoptilolite Micronized Zeolite", "1 tsp", "Cage-like aluminosilicate crystal structure; traps heavy metals and environmental toxins in lumen"],
            ["With Evening Meal", "TUDCA (Tauroursodeoxycholic Acid)", "250–500 mg", "Stimulates hydrophilic bile flow, preventing biliary sludge and accelerating hepatic metal output"],
            ["Bedtime", "Liposomal Glutathione", "500 mg", "Master intracellular antioxidant; conjugates heavy metals for renal and biliary excretion"]
        ],
        "timeline": [
            ("Week 1 — Biliary Activation", "TUDCA and ionic minerals open hepatic bile flow and restore cellular mineral voltage. Bowel motility accelerates."),
            ("Week 2 — Tissue Mobilization", "Modified Citrus Pectin and Zeolite bind circulating metals. Mild transient clearing sensations signify deep tissue metal displacement."),
            ("Week 3–4 — Enzymatic Re-ignition", "Essential minerals re-occupy active enzyme pockets. Superoxide Dismutase (SOD) and mitochondrial respiration voltage restore to youthful baselines.")
        ],
        "bigger_picture": (
            "The Dark Mirror clears the hidden sediment of time. Restoring pristine mineral balance reactivates human cellular enzymes, "
            "allowing your bioenergetic architecture to function with unhindered coherence."
        )
    }
]


def build_pdf(guide):
    filepath = DEST_DIR / guide["slug"]
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=letter,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=f"{guide['title']} — Spiral of Cellular Light",
        author="Spiral of Cellular Light — Certified Regenerative Health Program",
        creator="Spiral of Cellular Light"
    )

    styles = getSampleStyleSheet()

    # Custom Luminous Color Palette
    ink_color = colors.HexColor("#0B0F19")
    saffron_gold = colors.HexColor("#D97706")
    dark_gold = colors.HexColor("#B45309")
    cream_bg = colors.HexColor("#FFFBEB")
    paper_bg = colors.HexColor("#F7F5F0")
    muted_gray = colors.HexColor("#374151")

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=ink_color,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=dark_gold,
        spaceAfter=12
    )

    summary_style = ParagraphStyle(
        'SummaryText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=10,
        leading=14.5,
        textColor=ink_color,
        spaceAfter=12
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=ink_color,
        spaceBefore=14,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=muted_gray,
        spaceAfter=8
    )

    principle_title_style = ParagraphStyle(
        'PrincipleTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13.5,
        textColor=ink_color,
        spaceBefore=6
    )

    btn_text_style = ParagraphStyle(
        'BtnText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor("#FFFFFF"),
        alignment=1
    )

    disc_style = ParagraphStyle(
        'DisclaimerText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor("#6B7280"),
        alignment=1,
        spaceBefore=8
    )

    th_style = ParagraphStyle('TH', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=ink_color)
    td_style = ParagraphStyle('TD', parent=styles['Normal'], fontName='Helvetica', fontSize=8.5, leading=11.5, textColor=muted_gray)

    story = []

    # --- PAGE 1: COVER MASTHEAD & POETIC INTRODUCTION ---
    header_table_data = [[
        Paragraph(f"<b>AGEWELL BRIEF FIELD GUIDE</b> · {guide['domain'].upper()}", ParagraphStyle('HeadTop', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=dark_gold)),
        Paragraph("<b>PREPARED BY SPIRAL OF CELLULAR LIGHT</b>", ParagraphStyle('HeadRight', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=muted_gray, alignment=2))
    ]]
    header_table = Table(header_table_data, colWidths=[4.0*inch, 3.4*inch])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    story.append(header_table)
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=1, color=dark_gold, spaceAfter=10))

    # Title & Subtitle
    story.append(Paragraph(f"{guide['emoji']} {guide['title']}", title_style))
    story.append(Paragraph(guide['subtitle'], subtitle_style))
    story.append(Paragraph(f"<b>Executive Summary:</b> {guide['summary']}", summary_style))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2DDD3"), spaceAfter=10))

    # Luminous Introduction
    story.append(Paragraph("Program Perspective & Biological Foundations", h2_style))
    story.append(Paragraph(guide['introduction'], body_style))

    # Two Phases
    story.append(Paragraph("The Two Phases of Clearing", h2_style))
    for title, desc in guide['two_phases']:
        story.append(Paragraph(f"<b>{title}</b>", principle_title_style))
        story.append(Paragraph(desc, body_style))

    # --- PAGE 2: THE THREE EXITS ---
    story.append(PageBreak())

    story.append(Paragraph("The Three Exits & Transport Pathways", h2_style))
    story.append(Paragraph("Toxins transformed by cellular metabolism must exit through three essential pathways. If any one exit stalls, the others cannot compensate fully:", body_style))
    for title, desc in guide['three_exits']:
        story.append(Paragraph(f"<b>{title}</b>", principle_title_style))
        story.append(Paragraph(desc, body_style))

    story.append(Spacer(1, 10))

    # FULLSCRIPT BANNER CARD ON PAGE 2
    banner_content = [
        [Paragraph(f"<b>VERIFIED PRACTITIONER PROTOCOL: {guide['fullscript_plan_name'].upper()}</b>", ParagraphStyle('B1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9.5, textColor=dark_gold))],
        [Paragraph("Order direct practitioner-grade formulations on Fullscript. Enjoy automatic monthly refills, verified quality, and practitioner oversight.", ParagraphStyle('B2', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12.5, textColor=ink_color))],
        [Spacer(1, 6)],
        [Paragraph(f'<a href="{guide["fullscript_url"]}"><b>Order Protocol on Fullscript Direct →</b></a>', btn_text_style)]
    ]
    banner_table = Table(banner_content, colWidths=[7.2*inch])
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), cream_bg),
        ('BOX', (0,0), (-1,-1), 1.5, saffron_gold),
        ('PADDING', (0,0), (-1,-1), 12),
        ('ALIGN', (0,3), (0,3), 'CENTER'),
        ('BACKGROUND', (0,3), (0,3), dark_gold),
        ('BOTTOMPADDING', (0,3), (0,3), 8),
        ('TOPPADDING', (0,3), (0,3), 8),
    ]))
    story.append(banner_table)

    # --- PAGE 3: FULL SUPPLEMENT SCHEDULE & DOSAGE TABLE ---
    story.append(PageBreak())

    story.append(Paragraph("Targeted Supplement Protocol & Daily Schedule", h2_style))
    story.append(Paragraph("Integrate targeted practitioner-grade formulations into your daily bio-rhythms:", body_style))

    table_data = []
    for row_idx, row in enumerate(guide['protocol_table']):
        if row_idx == 0:
            table_data.append([Paragraph(cell, th_style) for cell in row])
        else:
            table_data.append([Paragraph(cell, td_style) for cell in row])

    proto_table = Table(table_data, colWidths=[1.4*inch, 2.0*inch, 1.2*inch, 2.6*inch])
    proto_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), paper_bg),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2DDD3")),
        ('PADDING', (0,0), (-1,-1), 5),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(proto_table)

    # --- PAGE 4: WHAT TO EXPECT & THE BIGGER PICTURE ---
    story.append(PageBreak())

    story.append(Paragraph("What to Expect Across the Protocol", h2_style))
    for title, desc in guide['timeline']:
        story.append(Paragraph(f"<b>{title}</b>", principle_title_style))
        story.append(Paragraph(desc, body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("The Bigger Picture & Seasonal Integration", h2_style))
    story.append(Paragraph(guide['bigger_picture'], body_style))

    story.append(Spacer(1, 14))

    # FINAL FULLSCRIPT BANNER CARD ON PAGE 4
    story.append(banner_table)

    story.append(Spacer(1, 12))
    story.append(Paragraph(
        f'Fullscript Plan Link: <a href="{guide["fullscript_url"]}">{guide["fullscript_url"]}</a><br/><br/>'
        'Prepared by Spiral of Cellular Light — Certified Regenerative Health Program.<br/>'
        'Disclaimer: Agewell Brief receives practitioner affiliate commission on Fullscript orders at no added cost to you. Always consult your qualified healthcare practitioner before beginning any new health protocol.',
        disc_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✅ Generated Poetic Multi-Page PDF Field Guide: {filepath.name} ({filepath.stat().st_size} bytes)")

def main():
    print("📄 Building 6 Luminous, Poetic Multi-Page Monetized PDF Field Guides...\n")
    for guide in FIELD_GUIDES:
        build_pdf(guide)
    print("\n✨ All 6 Luminous PDF Field Guides successfully built and ready for subscriber downloads!")

if __name__ == "__main__":
    main()
