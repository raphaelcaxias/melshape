"""
views — Pacote de UI do Melshape.

Este pacote contém proxies para auth/, patient/, professional/,
components/ e shared/, que ficam na raiz do projeto.

Os submódulos (views.patient.home, etc.) são arquivos proxy reais
em views/patient/home.py que re-exportam de patient/home.py.
Isso evita imports circulares e o overhead do alias via sys.modules.
"""
