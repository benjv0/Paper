#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_overleaf.py - Genera main.tex autosuficiente y el paquete overleaf_paper.zip

Parte de IEEE_es.tex (fuente modular) y sustituye cada \\input{archivo} por el
contenido de archivo.tex (macros y tablas). Copia el resultado a main.tex,
a overleaf_paper/ junto con references.bib, IEEEtran.cls (si existe) y las
figuras PDF usadas, y rearma overleaf_paper.zip.

Uso:  python3 Paper/make_overleaf.py   (desde la raiz o desde Paper/)
"""
import os
import re
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "IEEE_es.tex")
OUT = os.path.join(HERE, "main.tex")
OVL = os.path.join(HERE, "overleaf_paper")
ZIP = os.path.join(HERE, "overleaf_paper.zip")


def inline_inputs(text):
    def repl(m):
        name = m.group(1)
        path = os.path.join(HERE, name if name.endswith(".tex") else name + ".tex")
        with open(path, encoding="utf-8") as f:
            body = f.read().rstrip("\n")
        if name == "macros":
            return "% ── Macros consolidadas ──\n" + body
        return body
    return re.sub(r"^\\input\{([^}]+)\}", repl, text, flags=re.M)


def main():
    with open(SRC, encoding="utf-8") as f:
        src = f.read()
    out = inline_inputs(src)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(out)

    os.makedirs(OVL, exist_ok=True)
    shutil.copy(OUT, os.path.join(OVL, "main.tex"))
    shutil.copy(os.path.join(HERE, "references.bib"), os.path.join(OVL, "references.bib"))
    figs = set(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", out))
    for fig in figs:
        shutil.copy(os.path.join(HERE, fig), os.path.join(OVL, fig))

    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(os.listdir(OVL)):
            z.write(os.path.join(OVL, name), arcname=name)
    print("main.tex regenerado; overleaf_paper/ y overleaf_paper.zip actualizados con:",
          ", ".join(sorted(os.listdir(OVL))))


if __name__ == "__main__":
    main()
