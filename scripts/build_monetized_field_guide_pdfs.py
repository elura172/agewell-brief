#!/usr/bin/env python3
"""Build rich, multi-page publication-grade PDF Field Guides with embedded clickable Fullscript affiliate links.

Generates 6 multi-page, high-design PDF Field Guides in public/downloads/field-guides/:
1. Living Waters (Fluid & Transport) -> Fullscript Living Waters Plan
2. Inner Garden (Gut Ecology) -> Fullscript Inner Garden Plan
3. Cell Shedding (Senescence & Renewal) -> Fullscript Cell Shedding Plan
4. Higher Flame (Metabolism & Respiration) -> Fullscript Higher Flame Plan
5. Luminous Mind (Cognition & Neural Coherence) -> Fullscript Luminous Mind Plan
6. Dark Mirror (Mineral & Bio-clearing) -> Fullscript Dark Mirror Plan
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
        "summary": "Water inside human tissue is not mere bulk fluid—it forms structured Exclusion Zone (EZ) water (H3O2) along hydrophilic cell membranes, driving vascular micro-circulation, lymphatic drainage, and cellular clearing.",
        "overview": "The human body is 60% to 70% water by mass, but at a molecular level, water molecules constitute over 99% of all molecules in cellular biology. Standard physiology often treats body water as a passive solvent. Modern biophysics reveals that biological water is an active, structured phase of matter that stores electric charge, absorbs radiant infrared energy, and drives non-cardiac vascular transport.",
        "mechanisms": [
            ("1. Interfacial EZ Water Formation (H3O2)", "When liquid water interfaces with hydrophilic cell membranes and protein surfaces, it reorganizes into a dense, crystalline Exclusion Zone (EZ) layer. EZ water excludes solutes, carries negative electrical potential (-100mV to -200mV), and acts as a biological battery powered by ambient infrared light."),
            ("2. Charge-Driven Vascular Flow", "Capillaries and lymphatic vessels are lined with hydrophilic endothelial glycocalyx. The negative charge of EZ water along vessel walls creates a continuous proton flow through the center of micro-vessels, propelling blood and lymph without relying entirely on cardiac mechanical pressure."),
            ("3. Hepatic & Renal Sequence Clearing", "Attempting deep cellular detoxification without optimized fluid transport leads to systemic toxic recirculation. Supporting Phase I and Phase II liver processing alongside proper ionic mineral hydration ensures toxins are safely conjugated and excreted through bile and renal urine.")
        ],
        "protocol_table": [
            ["Phase / Timing", "Intervention & Compound", "Target Mechanism & Purpose"],
            ["Morning (Upon Waking)", "Pure Electrolyte Matrix (Mg, K, HCO3)", "Restores cell membrane electrical potential and expands EZ water"],
            ["Mid-Morning", "Infrared Light Exposure (15-20 min)", "Infrared photons directly expand Exclusion Zone water layer volume"],
            ["With Lunch", "Phase I/II Hepatic Support (NAC, Milk Thistle)", "Stimulates hepatic glutathione synthesis and biliary toxin binding"],
            ["Evening", "Structured Ionic Hydration & Quercetin", "Maintains micro-circulatory flow during nocturnal repair cycles"]
        ],
        "lifestyle_practices": [
            "Sunrise Infrared Light Exposure: Spend 15 minutes outdoors at sunrise to absorb natural near-infrared wavelengths that expand EZ water.",
            "Hydrophilic Mineral Hydration: Drink room-temperature filtered water infused with unrefined mineral salt or ionic potassium-magnesium electrolytes.",
            "Vascular Hydrotherapy Pulsing: Alternate warm and cool water in the shower to stimulate capillary vasodilation and lymphatic pumping."
        ],
        "precautions": "Individuals with severe kidney disease, congestive heart failure, or electrolyte restrictions should consult their supervising physician before altering mineral or fluid intake schedules."
    },
    {
        "slug": "inner-garden-field-guide.pdf",
        "title": "Inner Garden Field Guide",
        "subtitle": "Gut Microbiome Ecology, SCFA Signaling & Mucosal Barrier Integrity",
        "emoji": "🌱",
        "domain": "Gut Microbiome Ecology",
        "fullscript_url": "https://ca.fullscript.com/s/spiraloflight/shop/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ0OQ==",
        "fullscript_plan_name": "Inner Garden Practitioner Protocol",
        "summary": "The human gut is a complex microbial ecosystem containing over 100 trillion organisms. Short-chain fatty acids (SCFA) like butyrate preserve mucosal epithelial integrity, regulate neuro-inflammation, and coordinate metabolic rate.",
        "overview": "The intestinal epithelium is a single-cell layer separating systemic circulation from trillions of lumenal bacteria, dietary antigens, and metabolic byproducts. When mucosal tight junctions break down ('leaky gut'), bacterial endotoxins such as Lipopolysaccharide (LPS) cross into the bloodstream, triggering systemic low-grade inflammation.",
        "mechanisms": [
            ("1. Mucosal Epithelial Barrier Integrity", "Tight junction proteins (zonulin, occludin, claudin-1) act as molecular gates. Short-chain fatty acids, specifically sodium butyrate, serve as the primary fuel source for colonocytes, stimulating mucin-2 (MUC2) production to reinforce the protective mucus layer."),
            ("2. Short-Chain Fatty Acid (SCFA) Cascades", "Microbial fermentation of non-digestible prebiotic fibers yields acetate, propionate, and butyrate. These SCFAs bind G-protein coupled receptors (GPR41, GPR43, GPR109A) on immune cells, down-regulating nuclear factor kappa B (NF-kB) inflammatory cascades."),
            ("3. Microbiome Circadian Rhythmicity", "Gut microbes exhibit distinct diurnal fluctuations in abundance and metabolic output. Aligning meal timing with circadian light cycles supports microbial diversity and prevents circadian metabolic disruption.")
        ],
        "protocol_table": [
            ["Phase / Timing", "Intervention & Compound", "Target Mechanism & Purpose"],
            ["Morning (Fasted)", "Spore-Based Soil Organism Probiotics", "Survives gastric acid to colonize lower intestine and promote diversity"],
            ["Before Meals", "Mucosal Barrier Repair (L-Glutamine, Zinc Carnosine)", "Heals intestinal epithelial cell linings and tight junction complexes"],
            ["With Meals", "Polyphenol & Prebiotic Matrix (Acacia, Cranberry)", "Feeds beneficial Keystone species like Akkermansia muciniphila"],
            ["Evening", "Concentrated Sodium Butyrate / SCFA Support", "Fuels colonocytes during nocturnal mucosal repair and gut-brain signaling"]
        ],
        "lifestyle_practices": [
            "30+ Plant Variety Weekly Target: Consume a wide diversity of colorful vegetables, herbs, nuts, and seeds to feed distinct microbial taxa.",
            "Fasting Window Alignment: Allow a 12-to-14 hour overnight gut rest window to enable the Migrating Motor Complex (MMC) to sweep intestinal debris.",
            "Stress & Vagal Tone Activation: Engage in slow diaphragmatic breathing before meals to stimulate parasympathetic vagal tone and digestive enzyme secretion."
        ],
        "precautions": "Patients with Active SIBO (Small Intestinal Bacterial Overgrowth) should introduce prebiotic fibers cautiously under direct practitioner supervision."
    },
    {
        "slug": "cell-shedding-field-guide.pdf",
        "title": "Cell Shedding Field Guide",
        "subtitle": "Targeted Senolytic Clearing, Autophagy Activation & SASP Reduction",
        "emoji": "🍃",
        "domain": "Senescence & Cellular Renewal",
        "fullscript_url": "https://ca.fullscript.com/s/spiraloflight/shop/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ1MA==",
        "fullscript_plan_name": "Cell Shedding Practitioner Protocol",
        "summary": "Senescent cells are damaged, non-dividing 'zombie' cells that accumulate with biological age, secreting pro-inflammatory SASP cytokines that degrade surrounding tissue architecture. Periodic senolytic clearing restores youthful tissue dynamics.",
        "overview": "Cellular senescence evolved as an essential anti-cancer mechanism, permanently halting the division of damaged cells. However, when senescent cell clearance falls behind accumulation, these lingering cells secrete a toxic cocktail of pro-inflammatory cytokines, chemokines, and matrix metalloproteinases known as the Senescence-Associated Secretory Phenotype (SASP).",
        "mechanisms": [
            ("1. Senolytic Disruption of Anti-Apoptotic Pathways", "Senescent cells survive by up-regulating Senescent Cell Anti-Apoptotic Pathways (SCAPs) involving BCL-2, BCL-XL, and PI3K/AKT. Plant flavonoids like Fisetin and Quercetin target these survival networks, triggering apoptosis specifically in senescent cells while sparing healthy tissue."),
            ("2. Pulsed vs. Continuous Interventions", "Unlike daily maintenance nutrients, senolytic interventions are administered in intermittent 'hit-and-run' pulses (e.g., 2 consecutive days per month). This clears senescent cell populations without impairing normal physiological tissue repair."),
            ("3. Lysosomal Autophagy & Mitophagy", "Autophagy is the lysosomal degradation process that recycles misfolded proteins and damaged mitochondria (mitophagy). Activating autophagy prevents precocious senescent cell conversion and maintains cellular bioenergetics.")
        ],
        "protocol_table": [
            ["Phase / Timing", "Intervention & Compound", "Target Mechanism & Purpose"],
            ["Pulse Days (Day 1-2)", "High-Dose Liposomal Fisetin & Quercetin", "Transiently disrupts SCAP survival networks to clear senescent cells"],
            ["Daily Maintenance", "Spermidine & Trehalose Autophagy Boosters", "Stimulates lysosomal degradation and autophagic cellular recycling"],
            ["Daily Maintenance", "SASP Dampeners (Curcumin, Boswellia, EGCG)", "Suppresses pro-inflammatory cytokine secretion from remaining senescent cells"],
            ["Post-Pulse (Day 3-30)", "NAD+ Precursors & Stem Cell Co-Factors", "Supports tissue regeneration and progenitor cell renewal after clearing"]
        ],
        "lifestyle_practices": [
            "Intermittent Pulsed Fasting: Practice 16-to-24 hour fasts periodically to deplete cellular nutrient sensors (mTOR) and trigger autophagic clearing.",
            "High-Intensity Interval Exercise: Brief bursts of intense exertion induce transient cellular stress followed by robust autophagic adaptation.",
            "Sauna Heat-Shock Protein Induction: Infrared or traditional sauna sessions (20 min at 80°C/175°F) induce heat-shock proteins (HSP70) to refold damaged proteins."
        ],
        "precautions": "High-dose senolytic protocols should be pulsed intermittently rather than taken continuously. Pregnant or nursing mothers should avoid senolytic protocols."
    },
    {
        "slug": "higher-flame-field-guide.pdf",
        "title": "Higher Flame Field Guide",
        "subtitle": "Metabolic Flexibility, Mitochondrial Respiration Voltage & Fuel Switching",
        "emoji": "🔥",
        "domain": "Metabolic Resilience & Mitochondria",
        "fullscript_url": "https://ca.fullscript.com/s/spiraloflight/shop/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ0NQ==",
        "fullscript_plan_name": "Higher Flame Practitioner Protocol",
        "summary": "Metabolic health is defined by metabolic flexibility—the capacity to seamlessly transition between carbohydrate oxidation and fatty acid oxidation based on fuel availability. High mitochondrial voltage (ΔΨm) powers cellular cellular longevity.",
        "overview": "Mitochondria produce over 90% of cellular adenosine triphosphate (ATP) through oxidative phosphorylation. Modern metabolic dysfunction (insulin resistance, metabolic rigidity) arises when nutrient oversupply causes mitochondrial electron transport chain overload, resulting in excessive reactive oxygen species (ROS) leakage and reduced respiratory efficiency.",
        "mechanisms": [
            ("1. Inner Mitochondrial Membrane Voltage (ΔΨm)", "The inner mitochondrial membrane maintains a electrical potential difference (-140mV to -180mV). This voltage gradient powers ATP synthase. Preserving membrane cardiolipin integrity maintains respiratory chain efficiency."),
            ("2. AMPK & Sirtuin Co-Activation Dynamics", "AMP-activated protein kinase (AMPK) acts as the cellular fuel gauge. When ATP decreases, AMPK activates SIRT1 and SIRT3 sirtuin enzymes, driving mitochondrial biogenesis (via PGC-1α) and GLUT4 glucose transporter expression."),
            ("3. Metabolic Substrate Switching", "Healthy cells burn glucose efficiently post-meal and rapidly switch to fatty acid beta-oxidation and ketone utilization during fasting, exercise, or sleep.")
        ],
        "protocol_table": [
            ["Phase / Timing", "Intervention & Compound", "Target Mechanism & Purpose"],
            ["30 min Before Meals", "Berberine HCl / D-Chiro-Inositol Blend", "Activates AMPK, improves insulin sensitivity, and reduces postprandial glucose"],
            ["Morning (Fasted)", "Mitochondrial Co-Factors (CoQ10, ALA, PQQ)", "Protects inner membrane voltage and promotes mitochondrial biogenesis"],
            ["Mid-Day", "NAD+ Boosters (Nicotinamide Riboside / NMN)", "Provides essential substrate for SIRT1/SIRT3 sirtuin deacetylase activation"],
            ["Evening", "Alpha-GPC & Carnitine Shuttle Matrix", "Facilitates long-chain fatty acid transport into mitochondria for nocturnal oxidation"]
        ],
        "lifestyle_practices": [
            "Post-Meal Zone 1 Walking: Take a 10-to-15 minute gentle walk immediately following meals to activate GLUT4 translocation without requiring insulin.",
            "Cold Thermogenesis Exposure: Cold showers or ice baths stimulate brown adipose tissue (BAT) non-shivering thermogenesis via UCP1 uncoupling.",
            "Time-Restricted Feeding (10-Hour Window): Consume all caloric intake within a consistent 10-hour daily window to support metabolic circadian rhythm."
        ],
        "precautions": "Individuals taking prescription blood glucose lowering medications (e.g., insulin, metformin) should monitor blood sugar closely when introducing AMPK-activating botanicals."
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
        "overview": "The human brain consumes 20% of the body's total metabolic energy despite comprising only 2% of total body mass. Because the central nervous system lacks traditional lymphatic vessels, waste clearance relies on the Glymphatic System—a specialized glial-vascular network active almost exclusively during deep NREM sleep.",
        "mechanisms": [
            ("1. Glymphatic CSF-ISF Fluid Exchange", "During slow-wave Delta sleep, cortical interstitial space increases by 60%, allowing cerebrospinal fluid (CSF) to wash rapidly through brain parenchyma via Aquaporin-4 (AQP4) water channels on astrocyte endfeet, flushing neurotoxic proteins."),
            ("2. Brain-Derived Neurotrophic Factor (BDNF)", "BDNF fuels neurogenesis, synaptic plasticity, and long-term potentiation in the hippocampus. Nootropic adaptogens and physical movement upregulate BDNF expression."),
            ("3. Subcellular Melatonin Antioxidant Cascades", "While pineal melatonin regulates circadian sleep cycles, mitochondria produce intracellular melatonin locally to neutralize neural oxidative stress during high metabolic activity.")
        ],
        "protocol_table": [
            ["Phase / Timing", "Intervention & Compound", "Target Mechanism & Purpose"],
            ["Morning", "BDNF Nootropic Adaptogens (Lion's Mane, Bacopa)", "Stimulates nerve growth factor (NGF), BDNF, and synaptic dendritic branching"],
            ["Mid-Day", "Phosphatidylserine & Citicoline (CDP-Choline)", "Supports neuronal cell membrane fluidity and acetylcholine synthesis"],
            ["60 min Before Bed", "Magnesium L-Threonate & Apigenin Matrix", "Crosses blood-brain barrier to enhance NREM slow-wave sleep and glymphatic flow"],
            ["Bedtime", "Low-Dose Sublingual Melatonin & L-Theanine", "Protects neuronal mitochondria and calms excitatory glutamate signaling"]
        ],
        "lifestyle_practices": [
            "Side Sleeping Position: Clinical neuroimaging shows lateral (side) sleeping position maximizes glymphatic clearance compared to supine (back) sleeping.",
            "Blue-Blocking Light Hygiene: Eliminate artificial blue light exposure 2 hours before sleep to preserve natural pineal melatonin pulse amplitude.",
            "432 Hz Solfeggio Audition: Listen to 432 Hz / 528 Hz acoustic entrainment audio before sleep to promote alpha/theta brainwave coherence."
        ],
        "precautions": "Always check for drug interactions when combining neuro-active herbs with prescription sedatives or antidepressant medications."
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
        "overview": "Toxic heavy metals (lead, mercury, cadmium, aluminum) and halogen compounds (fluorine, chlorine, bromine) accumulate in connective tissue, bone, and neural structures over decades. Because toxic metals share atomic radii with essential minerals, they displace vital co-factors (zinc, copper, magnesium, selenium) from active enzyme binding pockets.",
        "mechanisms": [
            ("1. Competitive Mineral Displacement", "Heavy metals bind sulfhydryl (-SH) groups on functional proteins, inhibiting master antioxidant enzymes like Superoxide Dismutase (SOD) and Glutathione Peroxidase. Supplying abundant bio-available ionic minerals displaces toxic metals from binding sites."),
            ("2. Biliary Excretion & Enterohepatic Recirculation Prevention", "Once toxic metals are mobilized from tissue, liver hepatocytes secrete them into bile. Without intestinal binding agents (binders), up to 90% of excreted metals can be re-absorbed through the gut wall."),
            ("3. Bio-Unavailable Copper & Iron Calcification", "Unbound, bio-unavailable copper and excess tissue iron create destructive Fenton reactions, producing hydroxyl free radicals. Restoring ceruloplasmin synthesis safely chaperones copper into cellular cytochrome c oxidase.")
        ],
        "protocol_table": [
            ["Phase / Timing", "Intervention & Compound", "Target Mechanism & Purpose"],
            ["Morning (Fasted)", "Fulvic & Humic Ionic Trace Mineral Complex", "Restores cellular mineral voltage and displaces bio-unavailable toxic elements"],
            ["Mid-Day (Between Meals)", "Clinical Binders (Modified Citrus Pectin, Zeolite)", "Binds circulating heavy metals in digestive tract to prevent enterohepatic re-absorption"],
            ["With Evening Meal", "TUDCA & Ox Bile Support Matrix", "Promotes bile flow and biliary excretion of fat-soluble conjugated toxins"],
            ["Bedtime", "Liposomal Glutathione & Metallothionein Inducer", "Upregulates intracellular heavy metal sequestration and renal clearance"]
        ],
        "lifestyle_practices": [
            "Infrared Sweat Depuration: Regular infrared sauna sessions mobilize heavy metals stored in adipose tissue, excreting them through sweat glands.",
            "Hydration with Ionic Bicarbonate: Drink mineral-rich water containing natural bicarbonates to maintain urinary pH above 6.5, optimizing renal metal excretion.",
            "Eliminate Environmental Sources: Audit home drinking water (reverse osmosis with remineralization) and personal care products for heavy metal contamination."
        ],
        "precautions": "Heavy metal clearing protocols should be undertaken gradually. Always ensure bowel movements are regular (1-2 times daily) before initiating binder therapies."
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

    # Custom Color Palette
    ink_color = colors.HexColor("#0B0F19")
    saffron_gold = colors.HexColor("#D97706")
    dark_gold = colors.HexColor("#B45309")
    cream_bg = colors.HexColor("#FFFBEB")
    paper_bg = colors.HexColor("#F7F5F0")
    muted_gray = colors.HexColor("#4B5563")

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

    # --- PAGE 1: COVER MASTHEAD & EXECUTIVE SUMMARY ---
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

    # Program Overview
    story.append(Paragraph("Framework Perspective & Clinical Context", h2_style))
    story.append(Paragraph(guide['overview'], body_style))

    # Physiological Mechanisms
    story.append(Paragraph("Cellular Mechanisms & Biophysical Principles", h2_style))
    for title, desc in guide['mechanisms']:
        story.append(Paragraph(f"<b>{title}</b>", principle_title_style))
        story.append(Paragraph(desc, body_style))

    # --- PAGE 2: STEP-BY-STEP PROTOCOL TABLE & FULLSCRIPT BANNER ---
    story.append(PageBreak())

    story.append(Paragraph("Structured Step-by-Step Protocol", h2_style))
    story.append(Paragraph("Integrate targeted practitioner-grade formulations into daily bio-rhythms:", body_style))

    # Table Formatting
    table_data = []
    for row_idx, row in enumerate(guide['protocol_table']):
        if row_idx == 0:
            table_data.append([Paragraph(cell, th_style) for cell in row])
        else:
            table_data.append([Paragraph(cell, td_style) for cell in row])

    proto_table = Table(table_data, colWidths=[1.8*inch, 2.5*inch, 2.9*inch])
    proto_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), paper_bg),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2DDD3")),
        ('PADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    story.append(proto_table)

    story.append(Spacer(1, 14))

    # CLICKABLE FULLSCRIPT AFFILIATE BANNER CARD
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

    # --- PAGE 3: LIFESTYLE PRACTICES & CLINICAL SAFETY ---
    story.append(PageBreak())

    story.append(Paragraph("Lifestyle, Circadian & Photobiomodulation Practices", h2_style))
    for practice in guide['lifestyle_practices']:
        story.append(Paragraph(f"• {practice}", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("Clinical Safety & Practitioner Guidance", h2_style))
    story.append(Paragraph(guide['precautions'], body_style))

    story.append(Spacer(1, 16))
    story.append(Paragraph(
        f'Fullscript Plan Link: <a href="{guide["fullscript_url"]}">{guide["fullscript_url"]}</a><br/><br/>'
        'Prepared by Spiral of Cellular Light — Certified Regenerative Health Program.<br/>'
        'Disclaimer: Agewell Brief receives practitioner affiliate commission on Fullscript orders at no added cost to you. Always consult your qualified healthcare practitioner before beginning any new health protocol.',
        disc_style
    ))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"✅ Generated Multi-Page PDF Field Guide: {filepath.name} ({filepath.stat().st_size} bytes)")

def main():
    print("📄 Building 6 Publication-Grade Multi-Page Monetized PDF Field Guides...\n")
    for guide in FIELD_GUIDES:
        build_pdf(guide)
    print("\n✨ All 6 Multi-Page PDF Field Guides successfully built and ready for subscriber downloads!")

if __name__ == "__main__":
    main()
