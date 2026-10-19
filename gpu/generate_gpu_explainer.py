#!/usr/bin/env python3
"""
generate_gpu_explainer.py
Generates a detailed technical PDF explaining the GPU SHA-256 parallelization.
Uses only the reportlab canvas path API (no polygon shortcut).
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.platypus.flowables import Flowable

# ─── Colour palette ──────────────────────────────────────────────────────────
DARK_BG     = HexColor("#0d1117")
CARD_BG     = HexColor("#161b22")
BORDER      = HexColor("#30363d")
GREEN       = HexColor("#2ea043")
GREEN_LIGHT = HexColor("#3fb950")
BLUE        = HexColor("#58a6ff")
BLUE_DARK   = HexColor("#1f6feb")
ORANGE      = HexColor("#f0883e")
RED         = HexColor("#f85149")
PURPLE      = HexColor("#bc8cff")
CYAN        = HexColor("#79c0ff")
TEXT_MAIN   = HexColor("#e6edf3")
TEXT_DIM    = HexColor("#8b949e")
YELLOW      = HexColor("#d29922")
WHITE       = HexColor("#ffffff")

PAGE_W, PAGE_H = A4


# ─── Helper: draw a filled triangle (arrow head) using PDF path ───────────────
def draw_triangle(c, x1, y1, x2, y2, x3, y3, fill_color):
    c.setFillColor(fill_color)
    p = c.beginPath()
    p.moveTo(x1, y1)
    p.lineTo(x2, y2)
    p.lineTo(x3, y3)
    p.close()
    c.drawPath(p, fill=1, stroke=0)


# ─── Custom Flowables ─────────────────────────────────────────────────────────

class CodeBlock(Flowable):
    def __init__(self, lines, width, lang=""):
        super().__init__()
        self.lines = lines
        self.block_width = width
        self.lang = lang
        self.lh = 13
        self.pad = 12
        self.height = len(lines) * self.lh + self.pad * 2 + 20

    def wrap(self, aw, ah):
        return self.block_width, self.height

    def draw(self):
        c = self.canv
        w, h = self.block_width, self.height
        c.setFillColor(DARK_BG)
        c.roundRect(0, 0, w, h, 6, fill=1, stroke=0)
        c.setFillColor(HexColor("#161b22"))
        c.roundRect(0, h - 22, w, 22, 6, fill=1, stroke=0)
        c.rect(0, h - 22, w, 11, fill=1, stroke=0)
        if self.lang:
            c.setFont("Courier-Bold", 8)
            c.setFillColor(TEXT_DIM)
            c.drawString(self.pad, h - 14, self.lang)
        c.setFont("Courier", 9)
        y = h - self.pad - 22
        for line in self.lines:
            c.setFillColor(TEXT_MAIN)
            c.drawString(self.pad, y, line)
            y -= self.lh
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.5)
        c.roundRect(0, 0, w, h, 6, fill=0, stroke=1)


class DataFlowDiagram(Flowable):
    """File → chunks → threads → hashes pipeline."""
    def __init__(self, width):
        super().__init__()
        self.width = width
        self.height = 165

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.setFillColor(CARD_BG)
        c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.5)
        c.roundRect(0, 0, w, h, 8, fill=0, stroke=1)

        # Title
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(CYAN)
        c.drawString(w - 170, h - 15, "Data-Level Parallelism")

        # File box
        c.setFillColor(BLUE_DARK)
        c.roundRect(10, h - 50, 110, 34, 5, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(WHITE)
        c.drawCentredString(65, h - 28, "Archivo 1 GB")
        c.setFont("Helvetica", 7)
        c.setFillColor(CYAN)
        c.drawCentredString(65, h - 40, "dummy_1GB.bin")

        # Down arrow from file
        c.setStrokeColor(TEXT_DIM)
        c.setLineWidth(1.5)
        c.line(65, h - 52, 65, h - 68)
        draw_triangle(c, 59, h - 68, 71, h - 68, 65, h - 78, TEXT_DIM)
        c.setFont("Helvetica-Oblique", 7)
        c.setFillColor(YELLOW)
        c.drawString(70, h - 60, "÷ chunk_size")

        # Chunk boxes
        chunks = [("64 KB", "[0]", GREEN), ("64 KB", "[1]", HexColor("#238636")),
                  ("64 KB", "[2]", HexColor("#196127")), ("...", "", TEXT_DIM),
                  ("64 KB", "[N-1]", ORANGE)]
        chunk_y = h - 115
        bw = 55
        gap = 8
        xs = []
        cx = 10
        for lbl, cid, col in chunks:
            if lbl == "...":
                c.setFont("Helvetica-Bold", 12)
                c.setFillColor(TEXT_DIM)
                c.drawString(cx + 4, chunk_y + 8, "···")
                xs.append(None)
                cx += 30
            else:
                c.setFillColor(col)
                c.roundRect(cx, chunk_y, bw, 26, 4, fill=1, stroke=0)
                c.setFont("Helvetica-Bold", 8)
                c.setFillColor(WHITE)
                c.drawCentredString(cx + bw/2, chunk_y + 15, lbl)
                c.setFont("Helvetica", 7)
                c.setFillColor(HexColor("#aaaaaa"))
                c.drawCentredString(cx + bw/2, chunk_y + 5, cid)
                xs.append(cx + bw/2)
                cx += bw + gap

        # Thread boxes
        thread_y = h - 150
        tcx = 10
        for i, (lbl, cid, col) in enumerate(chunks):
            if lbl == "...":
                tcx += 30
                continue
            # Arrow from chunk to thread
            c.setStrokeColor(col)
            c.setLineWidth(1)
            c.line(xs[i], chunk_y, xs[i], thread_y + 18)
            draw_triangle(c, xs[i]-4, thread_y+18, xs[i]+4, thread_y+18, xs[i], thread_y+12, col)
            # Thread box
            c.setFillColor(PURPLE)
            c.roundRect(tcx, thread_y, bw, 16, 3, fill=1, stroke=0)
            c.setFont("Helvetica", 7)
            c.setFillColor(WHITE)
            c.drawCentredString(tcx + bw/2, thread_y + 5, f"Thread {i}")
            tcx += bw + gap

        # Hash boxes
        hash_y = 8
        hcx = 10
        for i, (lbl, cid, col) in enumerate(chunks):
            if lbl == "...":
                c.setFont("Helvetica-Bold", 10)
                c.setFillColor(TEXT_DIM)
                c.drawString(hcx + 4, hash_y + 2, "···")
                hcx += 30
                continue
            # Arrow from thread to hash
            c.setStrokeColor(ORANGE)
            c.setLineWidth(0.8)
            c.line(hcx + bw/2, thread_y, hcx + bw/2, hash_y + 16)
            draw_triangle(c, hcx+bw/2-4, hash_y+16, hcx+bw/2+4, hash_y+16,
                         hcx+bw/2, hash_y+10, ORANGE)
            c.setFillColor(ORANGE)
            c.roundRect(hcx, hash_y, bw, 15, 3, fill=1, stroke=0)
            c.setFont("Helvetica", 7)
            c.setFillColor(WHITE)
            c.drawCentredString(hcx + bw/2, hash_y + 4, f"Hash_{i}")
            hcx += bw + gap


class SlidingWindowDiagram(Flowable):
    def __init__(self, width):
        super().__init__()
        self.width = width
        self.height = 175

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.setFillColor(CARD_BG)
        c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.5)
        c.roundRect(0, 0, w, h, 8, fill=0, stroke=1)

        half = w / 2 - 5

        # ── LEFT: v1 ──
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(RED)
        c.drawCentredString(half / 2, h - 15, "v1  —  w[64]  (64 registros)")
        c.setFont("Helvetica", 7)
        c.setFillColor(TEXT_DIM)
        c.drawCentredString(half / 2, h - 26, "~100 regs/thread → 2 bloques/SM → 33%")

        cw, ch = 7, 13
        row_colors = [GREEN, BLUE_DARK, BLUE_DARK, HexColor("#333344")]
        y0 = h - 52
        for row, rcol in enumerate(row_colors):
            for i in range(16):
                c.setFillColor(rcol)
                c.rect(12 + i*(cw+1), y0 - row*16, cw, ch, fill=1, stroke=0)
                if row == 0 and i % 4 == 0:
                    c.setFont("Helvetica", 5)
                    c.setFillColor(WHITE)
                    c.drawCentredString(12 + i*(cw+1)+cw/2, y0 - row*16 + 3, str(i))
        c.setFont("Helvetica", 7)
        c.setFillColor(TEXT_DIM)
        c.drawString(12, y0 - 4*16 - 10, "64 × 4 = 256 bytes = 64 registros")

        # Occupancy bar v1
        bar_y = 30
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(TEXT_DIM)
        c.drawString(12, bar_y + 12, "Ocupancia v1:")
        c.setFillColor(RED)
        c.rect(90, bar_y+2, 55, 12, fill=1, stroke=0)
        c.setFillColor(HexColor("#333344"))
        c.rect(145, bar_y+2, 110, 12, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(WHITE)
        c.drawCentredString(117, bar_y+7, "33%")

        # Divider
        c.setStrokeColor(BORDER)
        c.setLineWidth(1)
        c.line(half+5, 8, half+5, h-8)

        # ── RIGHT: v2 ──
        rx = half + 12
        bw = half - rx + half  # available width on right
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(GREEN_LIGHT)
        c.drawCentredString(rx + (w - rx)/2, h - 15, "v2  —  w[16]  (16 registros)")
        c.setFont("Helvetica", 7)
        c.setFillColor(TEXT_DIM)
        c.drawCentredString(rx + (w - rx)/2, h - 26, "~48 regs/thread → 5 bloques/SM → 83%")

        cw2 = 14
        ring_y = h - 62
        for i in range(16):
            col2 = GREEN if i < 4 else BLUE_DARK
            c.setFillColor(col2)
            c.roundRect(rx + i*(cw2+2), ring_y, cw2, 22, 3, fill=1, stroke=0)
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(WHITE)
            c.drawCentredString(rx + i*(cw2+2)+cw2/2, ring_y+12, f"w[{i}]")
            if i < 4:
                c.setFont("Helvetica", 5)
                c.setFillColor(HexColor("#cccccc"))
                c.drawCentredString(rx + i*(cw2+2)+cw2/2, ring_y+4, f"→w[{i+16}]")

        # Circular arrow
        arr_y = ring_y - 16
        c.setStrokeColor(YELLOW)
        c.setLineWidth(1.2)
        ring_total = 16*(cw2+2) - 2
        c.line(rx, arr_y+5, rx+ring_total, arr_y+5)
        c.line(rx+ring_total, arr_y+5, rx+ring_total, ring_y)
        draw_triangle(c, rx-5, arr_y+5, rx+5, arr_y+5, rx, ring_y-1, YELLOW)
        c.setFont("Helvetica-Oblique", 7)
        c.setFillColor(YELLOW)
        c.drawCentredString(rx + ring_total/2, arr_y - 6, "w[j%16] se sobreescribe → ahorra 48 registros")

        c.setFont("Helvetica", 7)
        c.setFillColor(GREEN_LIGHT)
        c.drawString(rx, arr_y - 18, "16 × 4 = 64 bytes = 16 registros")

        # Occupancy bar v2
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(TEXT_DIM)
        c.drawString(rx, bar_y + 12, "Ocupancia v2:")
        bar_full = w - rx - 20
        c.setFillColor(GREEN)
        c.rect(rx+83, bar_y+2, int(bar_full*0.83), 12, fill=1, stroke=0)
        c.setFillColor(HexColor("#333344"))
        c.rect(rx+83+int(bar_full*0.83), bar_y+2, bar_full - int(bar_full*0.83), 12, fill=1, stroke=0)
        c.setFont("Helvetica-Bold", 7)
        c.setFillColor(WHITE)
        c.drawCentredString(rx+83+int(bar_full*0.40), bar_y+7, "83%")


class PCIeStreamDiagram(Flowable):
    def __init__(self, width):
        super().__init__()
        self.width = width
        self.height = 148

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.setFillColor(CARD_BG)
        c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.5)
        c.roundRect(0, 0, w, h, 8, fill=0, stroke=1)

        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(CYAN)
        c.drawString(10, h - 16, "Triple CUDA Streams: Superposición H2D + Kernel + D2H")

        labels = ["Stream 0:", "Stream 1:", "Stream 2:"]
        h2d_cols = [BLUE_DARK, HexColor("#1a5799"), HexColor("#14446e")]
        ker_cols  = [GREEN,    HexColor("#196127"), HexColor("#0d4d1e")]
        d2h_cols  = [ORANGE,   HexColor("#8b4513"), HexColor("#6b3410")]

        bar_h = 17
        bx = 78
        bar_area = w - bx - 15
        seg = bar_area / 5.0

        for row in range(3):
            y = h - 42 - row * (bar_h + 8)
            offset = row * seg * 0.65

            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(TEXT_MAIN)
            c.drawString(10, y + 4, labels[row])

            # H2D
            c.setFillColor(h2d_cols[row])
            c.roundRect(bx + offset, y, seg, bar_h, 3, fill=1, stroke=0)
            c.setFont("Helvetica", 7)
            c.setFillColor(WHITE)
            c.drawCentredString(bx + offset + seg/2, y + 5, "H2D")

            # Kernel
            c.setFillColor(ker_cols[row])
            c.roundRect(bx + offset + seg, y, seg*1.1, bar_h, 3, fill=1, stroke=0)
            c.setFont("Helvetica-Bold", 7)
            c.setFillColor(WHITE)
            c.drawCentredString(bx + offset + seg + seg*0.55, y + 5, "KERNEL")

            # D2H
            c.setFillColor(d2h_cols[row])
            c.roundRect(bx + offset + seg*2.1, y, seg*0.7, bar_h, 3, fill=1, stroke=0)
            c.setFont("Helvetica", 7)
            c.setFillColor(WHITE)
            c.drawCentredString(bx + offset + seg*2.1 + seg*0.35, y + 5, "D2H")

        # Time axis
        ax_y = h - 107
        c.setStrokeColor(TEXT_DIM)
        c.setLineWidth(0.8)
        c.line(bx, ax_y, bx + bar_area, ax_y)
        draw_triangle(c, bx+bar_area, ax_y+4, bx+bar_area, ax_y-4, bx+bar_area+6, ax_y, TEXT_DIM)
        c.setFont("Helvetica-Oblique", 7)
        c.setFillColor(TEXT_DIM)
        c.drawString(bx + bar_area - 5, ax_y - 12, "Tiempo →")

        # Overlap box
        c.setStrokeColor(YELLOW)
        c.setLineWidth(1)
        ov_x = bx + seg * 0.65
        ov_w = seg * 1.8
        c.rect(ov_x, h - 100, ov_w, 56, fill=0, stroke=1)
        c.setFont("Helvetica-Oblique", 7)
        c.setFillColor(YELLOW)
        c.drawCentredString(ov_x + ov_w/2, h - 108, "zona de superposición")

        # Bottom comparison
        c.setFont("Helvetica", 8)
        c.setFillColor(RED)
        c.drawString(10, 26, "Sin streams (v1 E2E):   secuencial  →  2.60 GB/s")
        c.setFillColor(GREEN_LIGHT)
        c.drawString(10, 12, "Con 3 streams (v2 E2E): superpuesto →  4.61 GB/s  (+77%)")


class ThroughputChart(Flowable):
    def __init__(self, width):
        super().__init__()
        self.width = width
        self.height = 195

    def wrap(self, aw, ah):
        return self.width, self.height

    def draw(self):
        c = self.canv
        w, h = self.width, self.height
        c.setFillColor(CARD_BG)
        c.roundRect(0, 0, w, h, 8, fill=1, stroke=0)
        c.setStrokeColor(BORDER)
        c.setLineWidth(0.5)
        c.roundRect(0, 0, w, h, 8, fill=0, stroke=1)

        data = [
            ("CPU SW 1T",           0.19,  RED),
            ("CPU SW 4T",           0.74,  RED),
            ("CPU SHA-NI 1T",       1.76,  ORANGE),
            ("CPU SHA-NI 4T",       5.13,  ORANGE),
            ("GPU v1  256KB E2E",   2.60,  BLUE),
            ("GPU v1  256KB Kernel",7.41,  BLUE_DARK),
            ("GPU v2  64KB  E2E",   4.61,  GREEN),
            ("GPU v2  64KB  Kernel",16.81, GREEN_LIGHT),
        ]
        max_val = 18.0
        lbl_w = 132
        bar_area = w - lbl_w - 55
        bar_h = 16
        gap = 6
        top_y = h - 30

        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(CYAN)
        c.drawString(10, h - 16, "Throughput Comparativo  (GB/s, archivo 1 GB)")

        for i, (lbl, val, col) in enumerate(data):
            y = top_y - i * (bar_h + gap)
            bw = (val / max_val) * bar_area
            c.setFont("Helvetica", 8)
            c.setFillColor(TEXT_MAIN)
            c.drawRightString(lbl_w, y + 5, lbl)
            c.setFillColor(col)
            c.roundRect(lbl_w + 4, y, bw, bar_h, 3, fill=1, stroke=0)
            txt = f"{val:.2f} GB/s"
            c.setFont("Helvetica-Bold", 8)
            if bw > 52:
                c.setFillColor(WHITE)
                c.drawString(lbl_w + bw - 2 - c.stringWidth(txt, "Helvetica-Bold", 8), y + 5, txt)
            else:
                c.setFillColor(TEXT_MAIN)
                c.drawString(lbl_w + bw + 5, y + 5, txt)

        # Grid
        for v in [2, 4, 6, 8, 10, 12, 14, 16]:
            xg = lbl_w + 4 + (v / max_val) * bar_area
            c.setStrokeColor(BORDER)
            c.setLineWidth(0.3)
            c.line(xg, top_y - len(data)*(bar_h+gap), xg, top_y + bar_h)
            c.setFont("Helvetica", 6)
            c.setFillColor(TEXT_DIM)
            c.drawCentredString(xg, top_y - len(data)*(bar_h+gap) - 8, str(v))


# ─── Document builder ─────────────────────────────────────────────────────────

def build_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path, pagesize=A4,
        leftMargin=2*cm, rightMargin=2*cm,
        topMargin=2*cm, bottomMargin=2*cm,
    )
    styles = getSampleStyleSheet()
    BW = PAGE_W - 4*cm   # body width

    def S(name, **kw):
        return ParagraphStyle(name, parent=styles["Normal"], **kw)

    ts   = S("T",  fontSize=22, textColor=WHITE, fontName="Helvetica-Bold",
              alignment=TA_CENTER, leading=28, spaceAfter=4)
    ss   = S("S",  fontSize=13, textColor=CYAN,  fontName="Helvetica-Bold",
              alignment=TA_CENTER, spaceAfter=2)
    ms   = S("M",  fontSize=9,  textColor=TEXT_DIM, fontName="Helvetica",
              alignment=TA_CENTER, spaceAfter=8)
    h1   = S("H1", fontSize=14, textColor=CYAN,  fontName="Helvetica-Bold",
              spaceBefore=14, spaceAfter=6)
    h2   = S("H2", fontSize=11, textColor=GREEN_LIGHT, fontName="Helvetica-Bold",
              spaceBefore=10, spaceAfter=4)
    body = S("B",  fontSize=9,  textColor=TEXT_MAIN, fontName="Helvetica",
              leading=14, alignment=TA_JUSTIFY, spaceAfter=5)
    note = S("N",  fontSize=8,  textColor=YELLOW, fontName="Helvetica-Oblique",
              leading=12, spaceAfter=4)
    cap  = S("C",  fontSize=8,  textColor=TEXT_DIM, fontName="Helvetica-Oblique",
              alignment=TA_CENTER, spaceAfter=4)

    def HR():
        return HRFlowable(width="100%", color=BORDER, thickness=0.5,
                          spaceAfter=6, spaceBefore=6)
    def SP(n=6): return Spacer(1, n)
    def P(t, st=None): return Paragraph(t, st or body)

    def tbl(data, col_w, header_col=BLUE_DARK, highlight_last=False):
        t = Table(data, colWidths=col_w)
        style = [
            ("BACKGROUND", (0,0), (-1,0), header_col),
            ("TEXTCOLOR",  (0,0), (-1,0), WHITE),
            ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
            ("FONTSIZE",   (0,0), (-1,-1), 8),
            ("FONTNAME",   (0,1), (-1,-1), "Helvetica"),
            ("TEXTCOLOR",  (0,1), (-1,-1), TEXT_MAIN),
            ("ROWBACKGROUNDS", (0,1), (-1,-1), [CARD_BG, HexColor("#1a2230")]),
            ("GRID",       (0,0), (-1,-1), 0.4, BORDER),
            ("TOPPADDING", (0,0), (-1,-1), 4),
            ("BOTTOMPADDING",(0,0),(-1,-1), 4),
            ("LEFTPADDING", (0,0),(-1,-1), 5),
            ("RIGHTPADDING",(0,0),(-1,-1), 5),
            ("ALIGN",      (1,0), (-1,-1), "CENTER"),
        ]
        if highlight_last:
            style += [
                ("BACKGROUND",(0,-1),(-1,-1), HexColor("#0a2a10")),
                ("TEXTCOLOR", (0,-1),(-1,-1), GREEN_LIGHT),
                ("FONTNAME",  (0,-1),(-1,-1), "Helvetica-Bold"),
            ]
        t.setStyle(TableStyle(style))
        return t

    story = []

    # ── Cover ──────────────────────────────────────────────────────────────────
    story += [SP(10),
              P("Paralelización de SHA-256 en GPU", ts),
              P("Análisis técnico del acelerador criptográfico CUDA", ss),
              P("Intel Core i7-1255U  ·  NVIDIA GeForce RTX 2050 (GA107M, sm_86)  ·  CUDA 12.4", ms),
              HR(), SP(4)]

    # ── 1. El Problema ─────────────────────────────────────────────────────────
    story.append(P("1. El Problema Fundamental: SHA-256 es Secuencial por Diseño", h1))
    story.append(P(
        "SHA-256 aplica una <b>función de compresión iterativa de 64 rounds</b>. Cada round "
        "calcula un nuevo estado a partir del estado del round anterior. Esta <b>dependencia "
        "de datos en cadena</b> hace que sea imposible paralelizar los 64 rounds de un único "
        "hash SHA-256: el round N+1 no puede comenzar hasta que el round N haya terminado.", body))
    story.append(CodeBlock([
        "  state = IV                             // valores iniciales (constantes fijas)",
        "  for i in range(64):                    // cada round depende del anterior",
        "      t1 = h + Σ₁(e) + Ch(e,f,g) + K[i] + w[i]",
        "      t2 = Σ₀(a) + Maj(a,b,c)",
        "      (a,b,c,d,e,f,g,h) = (t1+t2, a, b, c, d+t1, e, f, g)",
        "  state += (a, b, c, d, e, f, g, h)     // ← resultado = entrada del siguiente",
        "",
        "  → Imposible paralelizar internamente: round N+1 requiere el estado del round N",
    ], BW, "Pseudocódigo SHA-256"))
    story.append(SP(4))

    # ── 2. La Solución ─────────────────────────────────────────────────────────
    story.append(HR())
    story.append(P("2. La Solución: Paralelismo entre Hashes (Data-Level Parallelism)", h1))
    story.append(P(
        "En lugar de paralelizar <i>dentro</i> de un hash, paralelizamos <i>entre</i> hashes. "
        "El archivo de 1 GB se divide en miles de <b>chunks de tamaño fijo</b>. Cada chunk es "
        "completamente independiente de los demás — no comparte estado ni resultados intermedios. "
        "Esto permite que la GPU calcule <b>miles de hashes SHA-256 simultáneamente</b>, uno por "
        "thread CUDA, sin ningún tipo de sincronización ni comunicación entre hilos.", body))
    story.append(P("Figura 1: Mapeo de chunks a CUDA threads (Data-Level Parallelism)", cap))
    story.append(DataFlowDiagram(BW))
    story.append(SP(4))
    story.append(P(
        "<b>Nota:</b> Esta estrategia se llama <b>Data Parallelism</b> o paralelismo embarazosamente "
        "paralelo ('embarrassingly parallel'). Es la misma técnica usada en minería de criptomonedas, "
        "verificación de bloques en blockchain, y aceleración de HMAC-SHA256 en servidores TLS de "
        "alta demanda.", note))

    # ── 3. Arquitectura ────────────────────────────────────────────────────────
    story.append(HR())
    story.append(P("3. Arquitectura CUDA de la RTX 2050 y Jerarquía de Ejecución", h1))
    story.append(P(
        "La NVIDIA GeForce RTX 2050 (GA107M) organiza su hardware en tres niveles anidados. "
        "El benchmark explota los tres niveles para maximizar el rendimiento:", body))

    hw_data = [
        ["Nivel Hardware",   "Unidad",                          "Cantidad RTX 2050",  "Rol en el benchmark"],
        ["GPU",              "SM (Streaming Multiprocessor)",   "16",                 "Unidad de proceso independiente"],
        ["SM",               "Warps (grupos de 32 threads)",   "48 máx / SM",        "Unidad de scheduling del SM"],
        ["Warp",             "CUDA Threads",                    "32",                 "Ejecutan el mismo código"],
        ["—",                "Registros por SM",                "65.536",             "Memoria privada ultrarrápida"],
        ["—",                "Threads concurrentes máx",        "24.576",             "16 SMs × 1.536 threads/SM"],
    ]
    story.append(tbl(hw_data, [3*cm, 5.5*cm, 3*cm, 5*cm]))
    story.append(SP(8))

    story.append(P("3.1 Grid-Stride Loop: Saturar los 16 SMs en Todo Momento", h2))
    story.append(P(
        "El kernel v1 lanzaba exactamente un thread por chunk. Con 256KB/chunk → 4.096 threads. "
        "Con 64KB/chunk → 16.384 threads. El kernel v2 lanza un número fijo de threads igual "
        "a la capacidad máxima del hardware, y cada thread procesa múltiples chunks en un "
        "<b>bucle con paso igual al total de threads lanzados (grid-stride loop)</b>:", body))
    story.append(CodeBlock([
        "__global__ void sha256_kernel_v2(",
        "    const uint8_t *d_in, uint8_t *d_out,",
        "    int chunk_size, long num_chunks)",
        "{",
        "    // Grid-stride: cada thread avanza de stride en stride",
        "    for (long idx = blockIdx.x * blockDim.x + threadIdx.x;",
        "         idx < num_chunks;",
        "         idx += gridDim.x * blockDim.x)    // ← stride = total threads",
        "    {",
        "        // Calcula SHA-256 del chunk idx en solitario, sin comunicación",
        "        sha256_hash_chunk(d_in + idx*chunk_size, chunk_size,",
        "                         d_out + idx*32);",
        "    }",
        "}",
    ], BW, "CUDA C — sha256_gpu_v2.cu (grid-stride kernel)"))
    story.append(SP(4))

    # ── 4. Ocupancia ──────────────────────────────────────────────────────────
    story.append(HR())
    story.append(P("4. La Optimización Central: Reducir Registros y Maximizar Ocupancia", h1))
    story.append(P(
        "La <b>ocupancia</b> (SM occupancy) mide qué fracción de los warps disponibles por SM "
        "están activos. Más warps activos = mejor capacidad de ocultar latencias de memoria. "
        "El cuello de botella de v1 era la <b>presión de registros</b>: el message schedule "
        "estándar requiere un array <code>w[64]</code> de 256 bytes = 64 registros de 32 bits "
        "por thread. Con ~100 registros totales y 256 threads/bloque = 25.600 registros/bloque. "
        "La RTX 2050 tiene 65.536 registros/SM → solo 2 bloques activos/SM = 33% de ocupancia.", body))
    story.append(P("Figura 2: Ventana deslizante w[16] vs w[64] estándar y efecto en la ocupancia", cap))
    story.append(SlidingWindowDiagram(BW))
    story.append(SP(6))

    occ_data = [
        ["Parámetro",               "v1 (Baseline)",    "v2 (Optimizado)",   "Delta"],
        ["Array message schedule",  "w[64] — 256 bytes","w[16] — 64 bytes",  "−192 bytes"],
        ["Registros totales/thread","~100",             "≤48 (maxrregcount)","−52 registros"],
        ["Bloques activos/SM",      "2",                "5",                 "+3 bloques"],
        ["Threads activos/SM",      "512 / 1.536",      "1.280 / 1.536",    "+768 threads"],
        ["Ocupancia estimada",      "33.3%",            "83.3%",             "+50 puntos %"],
        ["Throughput kernel 64 KB", "2.81 GB/s",        "16.81 GB/s",       "+499% 🔥"],
    ]
    story.append(tbl(occ_data, [4.5*cm, 3.2*cm, 3.5*cm, 3*cm], highlight_last=True))
    story.append(SP(6))

    story.append(P("4.1 La Fórmula de la Ventana Deslizante", h2))
    story.append(P(
        "La expansión del message schedule SHA-256 sigue la recurrencia:", body))
    story.append(CodeBlock([
        "// Estándar (v1): w[64] — necesita todas las 64 palabras en memoria",
        "for i in range(16, 64):",
        "    w[i] = σ₁(w[i-2]) + w[i-7] + σ₀(w[i-15]) + w[i-16]",
        "",
        "// Ventana deslizante (v2): w[16] circular — sobreescribe en-lugar",
        "for i in range(16, 64):",
        "    j = i % 16            // índice circular (0..15)",
        "    // w[j] antes del assignment == w[i-16]  (ya no se necesitará)",
        "    w[j] = σ₁(w[(i-2)%16]) + w[(i-7)%16] + σ₀(w[(i-15)%16]) + w[j]",
        "    // w[j] después del assignment == w[i]  ← correcto para este round",
    ], BW, "Message Schedule — Comparativa v1 vs v2"))
    story.append(SP(4))

    # ── 5. PCIe + Streams ─────────────────────────────────────────────────────
    story.append(HR())
    story.append(P("5. El Cuello de Botella PCIe y los Triple CUDA Streams", h1))
    story.append(P(
        "Aunque el kernel CUDA v2 alcanza <b>16.81 GB/s</b> de throughput criptográfico puro, "
        "el rendimiento End-to-End real del sistema es de <b>4.61 GB/s</b>. La diferencia se "
        "debe al bus <b>PCIe 3.0 ×16</b> que conecta la CPU (RAM) con la GPU (VRAM): el "
        "archivo de 1 GB debe transferirse antes de procesarse, y los 32 bytes de hash de cada "
        "chunk deben copiarse de vuelta. En la práctica, el ancho de banda efectivo de PCIe "
        "para este workload es de ~10 GB/s — un factor 11× menor que la memoria GDDR6 de la GPU.", body))
    story.append(CodeBlock([
        "  Throughput kernel puro  = 16.81 GB/s  (computación dentro de la VRAM)",
        "  Throughput E2E real     =  4.61 GB/s  (incluye H2D + kernel + D2H)",
        "  Eficiencia PCIe         =  4.61 / 16.81 = 27.4%",
        "",
        "  → El 72.6% del tiempo total se consume en transferencia de datos,",
        "    no en el cálculo criptográfico. El PCIe es el cuello de botella.",
    ], BW, "Análisis de rendimiento"))
    story.append(SP(4))
    story.append(P("Figura 3: Triple CUDA Streams — Superposición de Etapas", cap))
    story.append(PCIeStreamDiagram(BW))
    story.append(SP(6))
    story.append(P(
        "La RTX 2050 dispone de motores DMA independientes para transferencias H2D y D2H. "
        "Con 3 streams sobre 3 segmentos del archivo, se crea un pipeline donde: mientras "
        "el <b>kernel</b> procesa el segmento N, el <b>motor H2D</b> ya carga el segmento N+1 "
        "y el <b>motor D2H</b> descarga los hashes del segmento N-1 — todo en paralelo. "
        "Esto redujo el tiempo E2E en un +77% respecto a v1 (2.60 → 4.61 GB/s).", body))

    # ── 6. Resultados ─────────────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(P("6. Resultados Completos del Benchmark", h1))
    story.append(P("Figura 4: Throughput comparativo — todas las plataformas y configuraciones", cap))
    story.append(ThroughputChart(BW))
    story.append(SP(8))

    story.append(P("Tabla 1: Resultados consolidados (archivo 1 GB, Intel i7-1255U / RTX 2050)", h2))
    res_data = [
        ["Plataforma",       "Config.",   "Throughput",  "Speedup vs SW 1T", "Energía (J/GB)"],
        ["CPU SW (C puro)",  "1 Thread",  "189.7 MB/s",  "1.00×",           "69.76"],
        ["",                 "2 Threads", "372.2 MB/s",  "1.96×",           "44.23"],
        ["",                 "4 Threads", "735.7 MB/s",  "3.88×",           "32.89"],
        ["CPU SHA-NI",       "1 Thread",  "1.763 MB/s",  "9.29×",           "7.00"],
        ["",                 "2 Threads", "3.315 MB/s",  "17.47×",          "5.37"],
        ["",                 "4 Threads", "5.126 MB/s",  "27.02×",          "5.17"],
        ["GPU v1 (E2E)",     "4 KB",      "1.966 MB/s",  "10.4×",           "4.74"],
        ["",                 "256 KB",    "2.662 MB/s",  "14.0×",           "3.77"],
        ["GPU v1 (Kernel)",  "256 KB",    "7.588 MB/s",  "40.0×",           "1.32"],
        ["GPU v2 (E2E)",     "64 KB",     "4.717 MB/s",  "24.9×",           "2.16"],
        ["GPU v2 (Kernel)",  "64 KB",     "16.81 GB/s",  "88.6×",           "—"],
        ["GPU v2 (Kernel)",  "4 KB",      "11.57 GB/s",  "61.0×",           "1.90 ★"],
    ]
    rt = Table(res_data, colWidths=[3.5*cm, 2.3*cm, 2.8*cm, 2.8*cm, 2.6*cm])
    rt_style = [
        ("BACKGROUND", (0,0), (-1,0), BLUE_DARK),
        ("TEXTCOLOR",  (0,0), (-1,0), WHITE),
        ("FONTNAME",   (0,0), (-1,0), "Helvetica-Bold"),
        ("FONTSIZE",   (0,0), (-1,-1), 8),
        ("FONTNAME",   (0,1), (-1,-1), "Helvetica"),
        ("TEXTCOLOR",  (0,1), (-1,-1), TEXT_MAIN),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [CARD_BG, HexColor("#1a2230")]),
        ("GRID",       (0,0), (-1,-1), 0.4, BORDER),
        ("TOPPADDING", (0,0), (-1,-1), 4), ("BOTTOMPADDING",(0,0),(-1,-1), 4),
        ("LEFTPADDING",(0,0), (-1,-1), 5), ("RIGHTPADDING", (0,0),(-1,-1), 5),
        ("ALIGN",      (2,0), (-1,-1), "CENTER"),
        ("SPAN",       (0,1), (0,3)),
        ("SPAN",       (0,4), (0,6)),
        ("SPAN",       (0,7), (0,9)),
        ("VALIGN",     (0,0), (-1,-1), "MIDDLE"),
        ("BACKGROUND", (0,10),(-1,11), HexColor("#0a2a10")),
        ("TEXTCOLOR",  (0,10),(-1,11), GREEN_LIGHT),
        ("FONTNAME",   (0,10),(-1,11), "Helvetica-Bold"),
        ("BACKGROUND", (0,12),(-1,12), HexColor("#0a2a10")),
        ("TEXTCOLOR",  (0,12),(-1,12), GREEN_LIGHT),
        ("FONTNAME",   (0,12),(-1,12), "Helvetica-Bold"),
    ]
    rt.setStyle(TableStyle(rt_style))
    story.append(rt)
    story.append(SP(8))

    # ── 7. Las 8 Optimizaciones ────────────────────────────────────────────────
    story.append(P("7. Las 8 Optimizaciones del Kernel v2", h1))
    opts = [
        ("__constant__ K[64]",
         "Los 64 valores de la tabla K de SHA-256 se ubican en memoria constante de CUDA. "
         "Cuando todos los threads de un warp acceden al mismo valor K[i], el hardware emite "
         "una única transacción de memoria en lugar de 32 lecturas individuales (broadcast)."),
        ("Ventana deslizante w[16]",
         "El array del message schedule pasa de 64 a 16 palabras mediante escritura circular "
         "in-place. Ahorra 48 registros/thread, triplicando los warps activos por SM."),
        ("#pragma unroll 64 rounds",
         "El compilador emite los 64 rounds como código lineal (sin bucle). Elimina el overhead "
         "de saltos condicionales y permite al planificador de instrucciones maximizar el ILP."),
        ("__byte_perm() para carga big-endian",
         "La instrucción PTX 'sel.b32' convierte el orden de bytes de little-endian (x86) a "
         "big-endian (SHA-256) en un único ciclo de reloj, reemplazando 4 shifts + 3 ORs."),
        ("Padding block inline",
         "El bloque de padding SHA-256 (requerido por la especificación) se construye "
         "directamente como 16 valores uint32 en registros, sin array local en memoria."),
        ("Grid-stride loop",
         "En lugar de un thread por chunk, se lanza un grid fijo que satura todos los SMs. "
         "Cada thread procesa múltiples chunks en un bucle strideado, eliminando el overhead "
         "de launches adicionales y garantizando 100% de actividad de los 16 SMs."),
        ("Memoria pinned (cudaMallocHost)",
         "La memoria del host se reserva como page-locked (no paginable). Esto permite al "
         "motor DMA de la GPU acceder directamente a ella sin copia intermedia del SO, "
         "duplicando el ancho de banda efectivo en las transferencias PCIe asíncronas."),
        ("Triple CUDA Streams",
         "El archivo se divide en 3 segmentos. Cada segmento se procesa en un stream "
         "independiente, solapando H2D del segmento N+1 con el kernel del segmento N y "
         "el D2H del segmento N-1 en los motores DMA separados de la GPU."),
    ]
    for i, (title, desc) in enumerate(opts):
        story.append(P(
            f"<b>{i+1}. {title}:</b> {desc}", body))
        story.append(SP(2))

    # ── 8. Conclusiones ───────────────────────────────────────────────────────
    story.append(HR())
    story.append(P("8. Conclusiones", h1))
    conc = [
        ("<b>Tipo de paralelismo:</b> SHA-256 se paraleliza a nivel de datos (DLP), no a nivel "
         "de instrucción. Cada thread calcula un hash independiente; no hay comunicación "
         "entre threads ni sincronización de estado."),
        ("<b>La ocupancia es la métrica crítica:</b> El factor de mejora más grande (33%→83%) "
         "se obtuvo únicamente reduciendo los registros de 100 a 48 por thread. Esto ilustra "
         "que en kernels compute-bound, la presión de registros domina sobre la frecuencia "
         "de reloj o el número de SMs."),
        ("<b>El cuello de botella real es el PCIe:</b> La GPU logra 16.81 GB/s de cómputo "
         "pero solo 4.61 GB/s E2E. Para cargas de trabajo donde los datos residen en RAM de "
         "host, el PCIe es el límite sistémico — no la capacidad de cómputo de la GPU."),
        ("<b>Eficiencia energética:</b> GPU v2 logra 1.90 J/GB — 36.7× mejor que el software "
         "de CPU y 2.7× mejor que SHA-NI en 4 cores, con 10.7 W de consumo promedio."),
        ("<b>Chunk size óptimo cambia con la arquitectura:</b> v1 prefería 256 KB (más trabajo "
         "por thread compensaba la baja ocupancia); v2 prefiere 64 KB (más paralelismo ya que "
         "la alta ocupancia no requiere compensación por threads escasos)."),
    ]
    for i, txt in enumerate(conc):
        story.append(P(f"{i+1}. {txt}", body))
        story.append(SP(2))

    doc.build(story)
    print(f"[✓] PDF generado → {output_path}")


if __name__ == "__main__":
    out = "/home/benjamin-oyarzun/Escritorio/Paper/Pruebas/gpu/SHA256_GPU_Parallelization_Explainer.pdf"
    build_pdf(out)
