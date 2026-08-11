"""Config compartida por toda la suite: los tests de GUI (Etapa 8+) corren
con el backend Qt "offscreen" — no hace falta un display real ni Xvfb."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
