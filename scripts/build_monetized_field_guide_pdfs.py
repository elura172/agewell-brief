#!/usr/bin/env python3
"""Build publication-grade PDF Field Guides with embedded clickable Fullscript affiliate links.

Generates 6 high-design PDF Field Guides in public/downloads/field-guides/:
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
    SimpleDocTemplate, Paragraph, Spacer, HRFlowable, Table, TableStyle
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

DEST_DIR = Path(__file__).resolve().parent.parent / "public" / "downloads" / "field-guides"
DEST_DIR.mkdir(parents=True, exist_ok=True)

FIELD_GUIDES = [
    {
        "slug": "living-waters-field-guide.pdf",
        "title": "Living Waters Field Guide",
        "subtitle": "Fluid Dynamics, Interfacial EZ Water & Vascular Transport Kinetics",
        "emoji": "🌊",
        "domain": "Fluid & Micro-Circulation",
        "fullscript_url": "https://ca.fullscript.com/u/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ0NA==",
        "fullscript_plan_name": "Living Waters Practitioner Protocol",
        "summary": "Water inside human tissue is not mere bulk fluid—it forms structured Exclusion Zone (EZ) water (H3O2) along hydrophilic cell membranes, driving vascular micro-circulation and cellular clearing.",
        "principles": [
            ("1. Interfacial EZ Water Formation", "Hydrophilic cell surfaces structure intracellular water into viscous, gel-like Exclusion Zones that carry negative electric charge."),
            ("2. Charge-Driven Vascular Flow", "Radiant infrared light and cellular energy expand EZ water zones, propelling micro-vascular blood flow without relying solely on cardiac pumping."),
            ("3. Hepatic & Renal Sequence Clearing", "Supporting Phase I/II liver processing and renal hydration before intensive clearing prevents systemic toxic recirculation.")
        ],
        "protocol_elements": [
            "Pure Electrolyte Matrix (Magnesium, Potassium, Bicarbonate)",
            "Infrared Light Exposure & Sunrise Hydration Rituals",
            "Targeted Liver Transport Compounds (N-Acetyl Cysteine, Milk Thistle)",
            "Structured Mineral Hydration Schedule"
        ]
    },
    {
        "slug": "inner-garden-field-guide.pdf",
        "title": "Inner Garden Field Guide",
        "subtitle": "Gut Microbiome Ecology, SCFA Signaling & Mucosal Barrier Integrity",
        "emoji": "🌱",
        "domain": "Gut Microbiome Ecology",
        "fullscript_url": "https://ca.fullscript.com/u/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ0OQ==",
        "fullscript_plan_name": "Inner Garden Practitioner Protocol",
        "summary": "The gut is a living microbial rainforest where short-chain fatty acids (butyrate, acetate, propionate) communicate with the vagus nerve and regulate systemic immune signaling.",
        "principles": [
            ("1. Mucosal Lining Integrity", "Tight junction proteins (zonulin, occludin) protect systemic circulation from endotoxins like Lipopolysaccharide (LPS)."),
            ("2. Short-Chain Fatty Acid (SCFA) Cascades", "Microbial fermentation of fermentable fibers feeds colonocytes and regulates inflammatory gene expression."),
            ("3. Microbiome Circadian Rhythmicity", "Gut microbes follow daily light/dark oscillations that coordinate metabolic rate and neurotransmitter synthesis.")
        ],
        "protocol_elements": [
            "Spore-Based & Human-Origin Microbiota Strains",
            "Mucosal Barrier Repair (L-Glutamine, Zinc Carnosine, Deglycyrrhizinated Licorice)",
            "Prebiotic Diversity Blend (Acacia Fiber, Inulin, Polyphenols)",
            "Targeted Botanical Antimicrobials & SCFA Boosters"
        ]
    },
    {
        "slug": "cell-shedding-field-guide.pdf",
        "title": "Cell Shedding Field Guide",
        "subtitle": "Targeted Senolytic Clearing, Autophagy Activation & SASP Reduction",
        "emoji": "🍃",
        "domain": "Senescence & Cellular Renewal",
        "fullscript_url": "https://ca.fullscript.com/u/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ1MA==",
        "fullscript_plan_name": "Cell Shedding Practitioner Protocol",
        "summary": "As cells reach replicative exhaustion, some become 'zombie' senescent cells that secrete inflammatory SASP cytokines. Pulse-clearing senescent cells rejuvenates tissue function.",
        "principles": [
            ("1. Senescent Cell Burden", "Non-dividing senescent cells accumulate with age, degrading surrounding tissue architecture through pro-inflammatory SASP secretion."),
            ("2. Pulsed Senolytic Interventions", "Unlike daily supplements, senolytics work best in periodic pulses to eliminate senescent cells while preserving healthy progenitor cells."),
            ("3. Macro-Autophagy Recycling", "Clearing cellular debris through lysosomal degradation restores mitochondrial quality control and youthful cellular bioenergetics.")
        ],
        "protocol_elements": [
            "Flavonoid Senolytics (Quercetin, Fisetin, Luteolin)",
            "Autophagy Activators (Spermidine, Resveratrol, Trehalose)",
            "SASP Cytokine Dampeners (Curcuminoids, Boswellia, Epigallocatechin Gallate)",
            "Intermittent Pulsed Fasting Protocols"
        ]
    },
    {
        "slug": "higher-flame-field-guide.pdf",
        "title": "Higher Flame Field Guide",
        "subtitle": "Metabolic Flexibility, Mitochondrial Respiration Voltage & Fuel Switching",
        "emoji": "🔥",
        "domain": "Metabolic Resilience & Mitochondria",
        "fullscript_url": "https://ca.fullscript.com/u/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ0NQ==",
        "fullscript_plan_name": "Higher Flame Practitioner Protocol",
        "summary": "Metabolic health is the capacity to seamlessly transition between burning glucose and fatty acids. High mitochondrial membrane potential (ΔΨm) sustains cellular ATP generation.",
        "principles": [
            ("1. Mitochondrial Membrane Potential (ΔΨm)", "The inner mitochondrial membrane maintains a voltage gradient (-140mV to -180mV) that drives the electron transport chain."),
            ("2. Substrate Switching Dynamics", "Healthy metabolism easily toggles between carbohydrate oxidation post-meal and beta-oxidation during fasting or exertion."),
            ("3. AMPK & sirtuin Pathway Co-Activation", "Energy sensors (AMPK, SIRT1, SIRT3) orchestrate mitochondrial biogenesis and GLUT4 glucose transporter translocation.")
        ],
        "protocol_elements": [
            "Mitochondrial Co-Factors (CoQ10 Ubiquinol, Alpha-Lipoic Acid, PQQ)",
            "AMPK Activators (Berberine HCl, Gynostemma Pentaphyllum, D-Chiro-Inositol)",
            "NAD+ Precursors (Nicotinamide Riboside / NMN Support)",
            "Cold Exposure & Non-Shivering Thermogenesis Protocols"
        ]
    },
    {
        "slug": "luminous-mind-field-guide.pdf",
        "title": "Luminous Mind Field Guide",
        "subtitle": "Glymphatic Sleep Clearance, Neuro-Plasticity & Biophotonic Brain Coherence",
        "emoji": "⚡",
        "domain": "Cognitive & Neural Coherence",
        "fullscript_url": "https://ca.fullscript.com/u/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ0OA==",
        "fullscript_plan_name": "Luminous Mind Practitioner Protocol",
        "summary": "Brain health requires deep slow-wave sleep, during which Astrocyte-mediated glymphatic channels expand by 60% to flush metabolic waste (amyloid beta, tau) into lymphatic circulation.",
        "principles": [
            ("1. Glymphatic Fluid Drainage", "During deep NREM sleep, cerebrospinal fluid washes through brain parenchyma, removing metabolic metabolic side-products."),
            ("2. Brain-Derived Neurotrophic Factor (BDNF)", "Neuroplasticity depends on BDNF stimulation, synaptic spine turnover, and balanced GABA/glutamate neurotransmission."),
            ("3. Circadian Melatonin Pulsing", "Melatonin is a master mitochondrial antioxidant produced intracellularly, regulating neural energy balance beyond sleep timing.")
        ],
        "protocol_elements": [
            "Nootropic & Neuro-Protective Adaptogens (Lion's Mane Mushroom, Bacopa Monnieri, Phosphatidylserine)",
            "Deep Sleep & Glymphatic Support (Magnesium L-Threonate, Apigenin, L-Theanine)",
            "Brain Fuel Substrates (MCT Oil, Citicoline, Acetyl-L-Carnitine)",
            "Circadian Light Alignment & 432 Hz Sound Audition"
        ]
    },
    {
        "slug": "dark-mirror-field-guide.pdf",
        "title": "Dark Mirror Field Guide",
        "subtitle": "Mineral Balance, Heavy Metal Chelation & Deep Tissue Bio-Clearing",
        "emoji": "🪞",
        "domain": "Mineral Balance & Bio-Clearing",
        "fullscript_url": "https://ca.fullscript.com/u/plans/TXVsdGlQYXRpZW50UGxhbi0xMDQ1Nw==",
        "fullscript_plan_name": "Dark Mirror Practitioner Protocol",
        "summary": "Heavy metals and synthetic halogen minerals bind to cellular enzymes. Systematic mineral replacement coupled with natural chelators restores enzyme kinetics and cellular voltage.",
        "principles": [
            ("1. Toxic Mineral Displacement", "Heavy metals (lead, mercury, cadmium, aluminum) displace essential ionic minerals (zinc, copper, magnesium, selenium) from active enzyme sites."),
            ("2. Extracellular Binding & Biliary Elimination", "Natural chelators bind circulating heavy metals and route them safely into bile for fecal excretion without re-absorption."),
            ("3. Bio-Unavailable Mineral Balancing", "Restoring proper copper/zinc and calcium/magnesium ratios reactivates ceruloplasmin and endogenous SOD antioxidant enzymes.")
        ],
        "protocol_elements": [
            "Clinical Grade Mineral Chelators (Modified Citrus Pectin, Clinoptilolite Zeolite, Chlorella)",
            "Trace Mineral Replenishment Blend (Fulvic/Humic Minerals, Ionic Zinc, Copper Sebacate)",
            "Biliary Flow Support (TUDCA, Ox Bile, Dandelion Root)",
            "Glutathione & Metallothionein Induction Matrix"
        ]
    }
]

def build_pdf(guide):
    filepath = DEST_DIR / guide["slug"]
    doc = SimpleDocTemplate(
        str(filepath),
        pagesize=letter,
        leftMargin=0.55 * inch,
        rightMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.55 * inch
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
        fontSize=24,
        leading=28,
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
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=ink_color,
        spaceAfter=14
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=16,
        textColor=ink_color,
        spaceBefore=12,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=muted_gray,
        spaceAfter=8
    )

    principle_title_style = ParagraphStyle(
        'PrincipleTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=13,
        textColor=ink_color
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
        spaceBefore=10
    )

    story = []

    # Header Bar
    header_table_data = [[
        Paragraph(f"<b>AGEWELL BRIEF FIELD GUIDE</b> · {guide['domain'].upper()}", ParagraphStyle('HeadTop', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=dark_gold)),
        Paragraph("<b>PREPARED BY SPIRAL OF CELLULAR LIGHT</b>", ParagraphStyle('HeadRight', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=muted_gray, alignment=2))
    ]]
    header_table = Table(header_table_data, colWidths=[4.0*inch, 3.4*inch])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    story.append(header_table)
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=1, color=dark_gold, spaceAfter=12))

    # Title & Emoji
    story.append(Paragraph(f"{guide['emoji']} {guide['title']}", title_style))
    story.append(Paragraph(guide['subtitle'], subtitle_style))
    story.append(Paragraph(guide['summary'], summary_style))

    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2DDD3"), spaceAfter=10))

    # Core Biophysics Principles
    story.append(Paragraph("Core Biophysics Principles", h2_style))
    for title, desc in guide['principles']:
        story.append(Paragraph(f"<b>{title}</b>", principle_title_style))
        story.append(Paragraph(desc, body_style))
        story.append(Spacer(1, 2))

    story.append(Spacer(1, 6))

    # Protocol Formulations & Interventions
    story.append(Paragraph("Key Protocol Elements & Interventions", h2_style))
    for elem in guide['protocol_elements']:
        story.append(Paragraph(f"• {elem}", body_style))

    story.append(Spacer(1, 14))

    # --- CLICKABLE FULLSCRIPT AFFILIATE BANNER CARD ---
    banner_content = [
        [Paragraph(f"<b>VERIFIED PRACTITIONER PROTOCOL: {guide['fullscript_plan_name'].upper()}</b>", ParagraphStyle('B1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, textColor=dark_gold))],
        [Paragraph("Order direct practitioner-grade formulations on Fullscript. Enjoy automatic monthly refills, verified quality, and practitioner oversight.", ParagraphStyle('B2', parent=styles['Normal'], fontName='Helvetica', fontSize=9, leading=12, textColor=ink_color))],
        [Spacer(1, 6)],
        # Clickable Hyperlink Button
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

    story.append(Spacer(1, 10))
    story.append(Paragraph(
        f'Fullscript Link: <a href="{guide["fullscript_url"]}">{guide["fullscript_url"]}</a><br/>'
        'Prepared by Spiral of Cellular Light — Certified Regenerative Health Program. Agewell Brief receives practitioner affiliate commission on Fullscript orders at no added cost to you.',
        disc_style
    ))

    doc.build(story)
    print(f"✅ Generated PDF Field Guide: {filepath.name} ({filepath.stat().st_size} bytes)")

def main():
    print("📄 Building 6 High-Design Monetized PDF Field Guides with Fullscript Affiliate Links...\n")
    for guide in FIELD_GUIDES:
        build_pdf(guide)
    print("\n✨ All 6 PDF Field Guides successfully built and ready for subscriber downloads!")

if __name__ == "__main__":
    main()
