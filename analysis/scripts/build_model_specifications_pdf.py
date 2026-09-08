from pathlib import Path

from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import LongTable, Paragraph, SimpleDocTemplate, Spacer, TableStyle

rl_config.invariant = 1


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "paper" / "figures" / "model_technical_specifications.pdf"

INK = colors.HexColor("#172431")
NAVY = colors.HexColor("#17324D")
MUTED = colors.HexColor("#607080")
GRID = colors.HexColor("#D7E0E7")
PALE = colors.HexColor("#F5F7F9")
ROW_ALT = colors.HexColor("#FAFBFC")
PROVIDER_COLORS = {
    "OpenAI": colors.HexColor("#087F72"),
    "Anthropic": colors.HexColor("#A65300"),
    "Google": colors.HexColor("#2363C7"),
    "DeepSeek": colors.HexColor("#5B4BCE"),
    "SpaceXAI": colors.HexColor("#202124"),
}


FONT, FONT_BOLD = "Helvetica", "Helvetica-Bold"


ROWS = [
    {
        "provider": "OpenAI",
        "model": "GPT-5.6 Sol",
        "id": "gpt-5.6-sol",
        "release": "9 Jul 2026",
        "release_note": "GA; preview 26 Jun 2026",
        "parameters": "Not disclosed",
        "weights": "No",
        "architecture": "Closed frontier flagship; architecture undisclosed",
        "reasoning": "Configurable effort: none to max; benchmark: xhigh",
        "context": "1,050,000",
        "output": "128,000",
        "modalities": "Text, image to text",
        "cutoff": "16 Feb 2026 knowledge",
    },
    {
        "provider": "OpenAI",
        "model": "OpenAI o3",
        "id": "o3-2025-04-16",
        "release": "16 Apr 2025",
        "release_note": "dated snapshot",
        "parameters": "Not disclosed",
        "weights": "No",
        "architecture": "Closed o-series reasoning model; architecture undisclosed",
        "reasoning": "Native inference-time reasoning; benchmark: high",
        "context": "200,000",
        "output": "100,000",
        "modalities": "Text, image to text",
        "cutoff": "1 Jun 2024 knowledge",
    },
    {
        "provider": "OpenAI",
        "model": "GPT-4.1",
        "id": "gpt-4.1-2025-04-14",
        "release": "14 Apr 2025",
        "release_note": "dated snapshot",
        "parameters": "Not disclosed",
        "weights": "No",
        "architecture": "Closed general-purpose non-reasoning model",
        "reasoning": "No native reasoning step; benchmark: none",
        "context": "1,047,576",
        "output": "32,768",
        "modalities": "Text, image to text",
        "cutoff": "1 Jun 2024 knowledge",
    },
    {
        "provider": "Anthropic",
        "model": "Claude Fable 5",
        "id": "claude-fable-5",
        "release": "9 Jun 2026",
        "release_note": "GA; restored 1 Jul 2026",
        "parameters": "Not disclosed",
        "weights": "No",
        "architecture": "Closed Mythos-class safeguarded model",
        "reasoning": "Always-on adaptive thinking; benchmark: effort high",
        "context": "1,000,000",
        "output": "128,000",
        "modalities": "Text, image to text",
        "cutoff": "Jan 2026 reliable/training",
    },
    {
        "provider": "Anthropic",
        "model": "Claude Sonnet 4.5",
        "id": "claude-sonnet-4-5-20250929",
        "release": "29 Sep 2025",
        "release_note": "dated snapshot",
        "parameters": "Not disclosed",
        "weights": "No",
        "architecture": "Closed Sonnet-tier hybrid reasoning model",
        "reasoning": "Optional manual extended thinking; benchmark: provider default",
        "context": "200,000",
        "output": "64,000",
        "modalities": "Text, image to text",
        "cutoff": "Not disclosed",
    },
    {
        "provider": "Anthropic",
        "model": "Claude Haiku 4.5",
        "id": "claude-haiku-4-5-20251001",
        "release": "15 Oct 2025",
        "release_note": "API snapshot 1 Oct 2025",
        "parameters": "Not disclosed",
        "weights": "No",
        "architecture": "Closed small and low-latency tier",
        "reasoning": "Manual extended thinking, off by default; benchmark: not requested",
        "context": "200,000",
        "output": "64,000",
        "modalities": "Text, image to text",
        "cutoff": "Feb/Jul 2025 reliable/training",
    },
    {
        "provider": "Google",
        "model": "Gemini 3.5 Flash",
        "id": "gemini-3.5-flash",
        "release": "19 May 2026",
        "release_note": "GA",
        "parameters": "Not disclosed",
        "weights": "No",
        "architecture": "Closed multimodal Flash-tier model",
        "reasoning": "Configurable native thinking; benchmark: high",
        "context": "1,048,576",
        "output": "65,536",
        "modalities": "Text, image, video, audio, PDF to text",
        "cutoff": "Jan 2025 knowledge",
    },
    {
        "provider": "Google",
        "model": "Gemini 3.1 Pro Preview",
        "id": "gemini-3.1-pro-preview",
        "release": "19 Feb 2026",
        "release_note": "public preview",
        "parameters": "Not disclosed",
        "weights": "No",
        "architecture": "Closed multimodal Pro-tier model",
        "reasoning": "Configurable native thinking; benchmark: high",
        "context": "1,048,576",
        "output": "65,536",
        "modalities": "Text, image, video, audio, PDF to text",
        "cutoff": "Jan 2025 knowledge",
    },
    {
        "provider": "Google",
        "model": "Gemma 4 31B IT",
        "id": "gemma-4-31b-it",
        "release": "31 Mar 2026",
        "release_note": "API 2 Apr 2026",
        "parameters": "30.7B total; dense; 60 layers; about 550M vision encoder",
        "weights": "Yes; Apache 2.0",
        "architecture": "Dense decoder-only transformer; hybrid local/global attention",
        "reasoning": "Configurable thinking tokens; benchmark: disabled",
        "context": "256,000",
        "output": "Not specified",
        "modalities": "Text, image to text",
        "cutoff": "Jan 2025 training",
    },
    {
        "provider": "DeepSeek",
        "model": "DeepSeek V4 Flash",
        "id": "deepseek-v4-flash - thinking",
        "release": "24 Apr 2026",
        "release_note": "V4 preview",
        "parameters": "284B total; 13B active per token",
        "weights": "Yes",
        "architecture": "Mixture-of-Experts; DeepSeek Sparse Attention",
        "reasoning": "Dual thinking/non-thinking model; benchmark: thinking high",
        "context": "1,000,000",
        "output": "384,000",
        "modalities": "Text to text",
        "cutoff": "Not disclosed",
    },
    {
        "provider": "DeepSeek",
        "model": "DeepSeek V4 Flash",
        "id": "deepseek-v4-flash - no thinking",
        "release": "24 Apr 2026",
        "release_note": "same weights as above",
        "parameters": "284B total; 13B active per token",
        "weights": "Yes",
        "architecture": "Mixture-of-Experts; DeepSeek Sparse Attention",
        "reasoning": "Dual thinking/non-thinking model; benchmark: disabled",
        "context": "1,000,000",
        "output": "384,000",
        "modalities": "Text to text",
        "cutoff": "Not disclosed",
    },
    {
        "provider": "DeepSeek",
        "model": "DeepSeek V4 Pro",
        "id": "deepseek-v4-pro",
        "release": "24 Apr 2026",
        "release_note": "V4 preview",
        "parameters": "1.6T total; 49B active per token",
        "weights": "Yes",
        "architecture": "Mixture-of-Experts; DeepSeek Sparse Attention",
        "reasoning": "Dual thinking/non-thinking model; benchmark: thinking high",
        "context": "1,000,000",
        "output": "384,000",
        "modalities": "Text to text",
        "cutoff": "Not disclosed",
    },
    {
        "provider": "SpaceXAI",
        "model": "Grok 4.5",
        "id": "grok-4.5",
        "release": "16 Jul 2026",
        "release_note": "public launch",
        "parameters": "Not disclosed",
        "weights": "No",
        "architecture": "Closed frontier model; architecture undisclosed",
        "reasoning": "Configurable low/medium/high; benchmark: high",
        "context": "500,000",
        "output": "Not specified",
        "modalities": "Text, image to text",
        "cutoff": "1 Feb 2026 knowledge",
    },
    {
        "provider": "SpaceXAI",
        "model": "Grok 4.3",
        "id": "grok-4.3",
        "release": "By 6 May 2026*",
        "release_note": "first dated official use",
        "parameters": "Not disclosed",
        "weights": "No",
        "architecture": "Closed general-purpose model; architecture undisclosed",
        "reasoning": "Configurable none/low/medium/high; benchmark: high",
        "context": "1,000,000",
        "output": "Not specified",
        "modalities": "Text, image to text",
        "cutoff": "Not disclosed",
    },
]


def para(text, style):
    return Paragraph(text, style)


def build_pdf():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    page_width, _ = A4
    margin = 7 * mm
    usable_width = page_width - 2 * margin

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontName=FONT,
        fontSize=16,
        leading=18,
        textColor=NAVY,
        alignment=TA_LEFT,
        spaceAfter=3,
    )
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Normal"],
        fontName=FONT,
        fontSize=7.4,
        leading=8.7,
        textColor=MUTED,
        spaceAfter=7,
    )
    header_style = ParagraphStyle(
        "Header",
        parent=styles["Normal"],
        fontName=FONT_BOLD,
        fontSize=6.7,
        leading=7.8,
        textColor=NAVY,
        alignment=TA_LEFT,
    )
    cell_style = ParagraphStyle(
        "Cell",
        parent=styles["Normal"],
        fontName=FONT,
        fontSize=7.0,
        leading=8.1,
        textColor=INK,
        alignment=TA_LEFT,
    )
    small_style = ParagraphStyle(
        "Small",
        parent=cell_style,
        fontSize=6.3,
        leading=7.3,
        textColor=MUTED,
    )
    note_style = ParagraphStyle(
        "Note",
        parent=styles["Normal"],
        fontName=FONT,
        fontSize=5.8,
        leading=7.0,
        textColor=MUTED,
        spaceBefore=2,
    )

    doc = SimpleDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=7 * mm,
        bottomMargin=7 * mm,
        title="Technical specifications of the evaluated models",
        author="Benchmark analysis",
        subject="A priori technical comparison of benchmark model configurations - portrait layout",
    )

    story = [
        para("Technical specifications of the evaluated models", title_style),
        para(
            "A priori comparison of the 14 benchmark configurations. No benchmark outcome is included. "
            "Token limits and model status refer to first-party documentation available on 10 Aug 2026.",
            subtitle_style,
        ),
    ]

    headers = [
        "Model / API identifier",
        "Public release",
        "Parameters",
        "Open weights",
        "Architecture / model class",
        "Reasoning capability / benchmark mode",
        "Context window",
        "Maximum output",
        "Knowledge / training cutoff",
    ]
    data = [[para(item, header_style) for item in headers]]

    for row in ROWS:
        provider_color = PROVIDER_COLORS[row["provider"]].hexval()
        model = (
            f'<font name="{FONT_BOLD}" color="{provider_color}">{row["model"]}</font><br/>'
            f'<font size="5.8" color="#607080">{row["provider"].upper()}</font><br/>'
            f'<font name="Courier" size="5.4" color="#7B8995">{row["id"]}</font>'
        )
        release = f'<font name="{FONT_BOLD}">{row["release"]}</font><br/><font color="#607080">{row["release_note"]}</font>'
        data.append(
            [
                para(model, cell_style),
                para(release, cell_style),
                para(row["parameters"], cell_style),
                para(row["weights"], cell_style),
                para(row["architecture"], cell_style),
                para(row["reasoning"], cell_style),
                para(row["context"], cell_style),
                para(row["output"], cell_style),
                para(row["cutoff"], small_style),
            ]
        )

    proportions = [1.65, 1.0, 1.1, 0.6, 1.35, 1.5, 0.78, 0.78, 1.0]
    unit = usable_width / sum(proportions)
    col_widths = [unit * value for value in proportions]
    table = LongTable(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")

    table_style = [
        ("BACKGROUND", (0, 0), (-1, 0), PALE),
        ("TEXTCOLOR", (0, 0), (-1, 0), NAVY),
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor("#BFCBD4")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 2.3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.3),
        ("TOPPADDING", (0, 0), (-1, 0), 4.2),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4.2),
        ("TOPPADDING", (0, 1), (-1, -1), 2.8),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 2.8),
        ("LINEBELOW", (0, 1), (-1, -1), 0.28, GRID),
    ]

    provider_start_indices = []
    prior_provider = None
    for index, row in enumerate(ROWS, start=1):
        if index % 2 == 0:
            table_style.append(("BACKGROUND", (0, index), (-1, index), ROW_ALT))
        if row["provider"] != prior_provider:
            provider_start_indices.append(index)
            table_style.append(("LINEABOVE", (0, index), (-1, index), 1.15, PROVIDER_COLORS[row["provider"]]))
        table_style.append(("LINEBEFORE", (0, index), (0, index), 2.2, PROVIDER_COLORS[row["provider"]]))
        prior_provider = row["provider"]

    table.setStyle(TableStyle(table_style))
    story.append(table)
    story.append(Spacer(1, 4))
    story.append(
        para(
            "* SpaceXAI provides no dedicated dated launch announcement for Grok 4.3; 6 May 2026 is the earliest "
            "dated official production reference identified. 'Not disclosed' is used when the developer publishes no "
            "official value; no third-party parameter estimates are included. The two V4 Flash rows are separate "
            "benchmark configurations of the same model weights.",
            note_style,
        )
    )
    story.append(
        para(
            "Primary sources: OpenAI model documentation; Anthropic model overview and release notes; Gemini API "
            "model and deprecation documentation; Gemma 4 model card; DeepSeek V4 release and pricing documentation; "
            "SpaceXAI model documentation.",
            note_style,
        )
    )

    def page_footer(canvas, document):
        canvas.saveState()
        canvas.setStrokeColor(GRID)
        canvas.setLineWidth(0.4)
        canvas.line(document.leftMargin, 5.7 * mm, page_width - document.rightMargin, 5.7 * mm)
        canvas.setFont(FONT, 5.8)
        canvas.setFillColor(MUTED)
        canvas.drawString(document.leftMargin, 3.5 * mm, "Benchmark model specifications")
        canvas.drawRightString(page_width - document.rightMargin, 3.5 * mm, f"Page {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=page_footer, onLaterPages=page_footer)


if __name__ == "__main__":
    build_pdf()
    print(OUTPUT)
