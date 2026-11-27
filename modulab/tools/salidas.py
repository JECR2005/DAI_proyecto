"""generar_configuracion y generar_cotizacion_pdf.

STUBS de Gustavo: funcionan para la rebanada (config.json real y una
maqueta HTML sencilla; cotización borrador en texto). Gustavo los
reemplaza por la maqueta Jinja2 y el PDF de ReportLab sin cambiar las
firmas: reciben ids de módulo, nunca precios (los precios salen del CSV).
"""
from __future__ import annotations

import html
import json
import re

from pydantic import BaseModel, Field

from .. import config
from . import datos
from .catalogo import cerrar_dependencias


def _carpeta():
    carpeta = datos.carpeta_sesion.get()
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def lineas_de(modulos: list[str]) -> list[dict]:
    """Base + módulos + dependencias, con precios del CSV, sin lo que el negocio ya tiene contratado."""
    finales, _, _ = cerrar_dependencias(config.MODULOS_BASE + modulos)
    contratados = set(datos.contratados_actual.get())
    precios = datos.precios()
    return [{"id": m, "nombre": precios[m]["nombre"], "precio": precios[m]["precio"]}
            for m in finales if m not in contratados]


class SeccionConfig(BaseModel):
    id: str = Field(description="Id del módulo (uno de los que tendrá el sitio)")
    titulo: str = Field(max_length=60, description="Título de la sección en el lenguaje del negocio")
    texto: str = Field(max_length=300, description="Una o dos frases para el cliente final, sin precios")


class ArgsGenerarConfiguracion(BaseModel):
    modulos: list[str] = Field(description="Ids de los módulos adicionales elegidos (sin los 3 base)")
    giro: str = Field(description="Giro del negocio")
    nombre_negocio: str = Field(default="Mi negocio", description="Nombre de ejemplo para la maqueta")
    bienvenida: str = Field(default="", max_length=300, description="Texto de bienvenida del sitio, sin precios")
    secciones: list[SeccionConfig] = Field(
        default_factory=list, description="Título y texto por módulo, en el orden en que deben aparecer")


_PRECIO = re.compile(r"\$|\d[\d,.]*\s*(pesos|mxn)\b", re.IGNORECASE)


def generar_configuracion(args: ArgsGenerarConfiguracion) -> dict:
    catalogo = datos.modulos()
    # El sitio muestra todo lo que tendrá el negocio: lo ya contratado más lo nuevo.
    finales, _, no_existen = cerrar_dependencias(config.MODULOS_BASE + list(datos.contratados_actual.get())
                                                 + args.modulos)
    if no_existen:
        return {"error": f"Módulos inexistentes: {no_existen}"}
    # El Configurador solo adapta textos y orden: no agrega módulos ni escribe precios.
    ajenos = [s.id for s in args.secciones if s.id not in finales]
    if ajenos:
        return {"error": f"Secciones de módulos que el sitio no tendrá: {ajenos}. Usa solo {finales}."}
    textos = [args.bienvenida] + [t for s in args.secciones for t in (s.titulo, s.texto)]
    if any(_PRECIO.search(t) for t in textos):
        return {"error": "Los textos no pueden incluir precios ni montos; el precio lo pone la cotización."}
    propias = {s.id: s for s in args.secciones}
    orden = [s.id for s in args.secciones] + [m for m in finales if m not in propias]
    secciones_cfg = [{"id": m, "modulo": catalogo[m]["nombre"],
                      "titulo": propias[m].titulo if m in propias else catalogo[m]["nombre"],
                      "texto": propias[m].texto if m in propias else catalogo[m]["descripcion"],
                      "activo": True} for m in orden]
    configuracion = {"negocio": args.nombre_negocio, "giro": args.giro, "bienvenida": args.bienvenida,
                     "modulos": secciones_cfg}
    carpeta = _carpeta()
    ruta_json = carpeta / "config.json"
    ruta_json.write_text(json.dumps(configuracion, ensure_ascii=False, indent=2), encoding="utf-8")
    menu = "".join(f"<li>{html.escape(s['titulo'])}</li>" for s in secciones_cfg)
    bienvenida = f"<p>{html.escape(args.bienvenida)}</p>" if args.bienvenida else ""
    secciones = "".join(
        f"<section><h2>{html.escape(s['titulo'])}</h2><p>{html.escape(s['texto'])}</p>"
        f"<p><em>Datos de ejemplo.</em></p></section>" for s in secciones_cfg)
    ruta_html = carpeta / "maqueta.html"
    ruta_html.write_text(
        f"<!DOCTYPE html><html lang='es'><meta charset='utf-8'><title>{html.escape(args.nombre_negocio)}</title>"
        f"<body><header><h1>{html.escape(args.nombre_negocio)}</h1>{bienvenida}<nav><ul>{menu}</ul></nav></header>"
        f"{secciones}<footer>Maqueta generada por ModuLab</footer></body></html>", encoding="utf-8")
    return {"config_json": str(ruta_json), "maqueta_html": str(ruta_html), "modulos_activos": finales}


class ArgsGenerarCotizacionPdf(BaseModel):
    modulos: list[str] = Field(description="Ids de los módulos adicionales elegidos (sin los 3 base)")


def generar_cotizacion_pdf(args: ArgsGenerarCotizacionPdf) -> dict:
    lineas = lineas_de(args.modulos)
    total = sum(l["precio"] for l in lineas)
    texto = ["COTIZACIÓN — BORRADOR (sin folio, no vale como cotización emitida)", ""]
    texto += [f"{l['id']}  {l['nombre']:<34} ${l['precio']:>9,.2f}" for l in lineas]
    texto += ["", f"{'TOTAL':<39} ${total:>9,.2f}"]
    ruta = _carpeta() / "cotizacion_borrador.txt"
    ruta.write_text("\n".join(texto), encoding="utf-8")
    return {"archivo": str(ruta), "total_mxn": total, "lineas": len(lineas),
            "nota": "Borrador sin folio. Emitir requiere confirmación humana."}


def generar_documento_oficial(lineas: list[dict], folio: str, fecha: str, vigencia: str) -> str:
    """Cotización oficial con folio y vigencia (PDF con ReportLab; texto si no está instalado).

    STUB de Gustavo: él la reemplaza por el diseño final del PDF sin cambiar la firma.
    """
    carpeta = _carpeta()
    total = sum(l["precio"] for l in lineas)
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except ImportError:
        ruta = carpeta / f"{folio}.txt"
        texto = [f"COTIZACIÓN {folio}", f"Fecha: {fecha[:10]}   Vigencia: hasta {vigencia}", ""]
        texto += [f"{l['id']}  {l['nombre']:<34} ${l['precio']:>9,.2f}" for l in lineas]
        texto += ["", f"{'TOTAL':<39} ${total:>9,.2f}"]
        ruta.write_text("\n".join(texto), encoding="utf-8")
        return str(ruta)
    ruta = carpeta / f"{folio}.pdf"
    c = canvas.Canvas(str(ruta), pagesize=letter)
    _, alto = letter
    y = alto - 72
    c.setFont("Helvetica-Bold", 16)
    c.drawString(72, y, f"Cotización {folio}")
    c.setFont("Helvetica", 10)
    y -= 20
    c.drawString(72, y, f"Fecha: {fecha[:10]}    Vigente hasta: {vigencia}")
    y -= 30
    c.setFont("Helvetica-Bold", 10)
    c.drawString(72, y, "Módulo")
    c.drawRightString(540, y, "Precio (MXN)")
    c.setFont("Helvetica", 10)
    for l in lineas:
        y -= 16
        c.drawString(72, y, f"{l['id']}  {l['nombre']}")
        c.drawRightString(540, y, f"${l['precio']:,.2f}")
    y -= 24
    c.setFont("Helvetica-Bold", 11)
    c.drawString(72, y, "Total")
    c.drawRightString(540, y, f"${total:,.2f}")
    c.setFont("Helvetica", 8)
    c.drawString(72, 60, "Cotización emitida por ModuLab. Precios de la lista oficial del desarrollador.")
    c.save()
    return str(ruta)
