"""generar_configuracion y generar_cotizacion_pdf.

STUBS de Gustavo: funcionan para la rebanada (config.json real y una
maqueta HTML sencilla; cotización borrador en texto). Gustavo los
reemplaza por la maqueta Jinja2 y el PDF de ReportLab sin cambiar las
firmas: reciben ids de módulo, nunca precios (los precios salen del CSV).
"""
from __future__ import annotations

import html
import json

from pydantic import BaseModel, Field

from .. import config
from . import datos
from .catalogo import cerrar_dependencias


def _carpeta():
    carpeta = datos.carpeta_sesion.get()
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def lineas_de(modulos: list[str]) -> list[dict]:
    """Base + módulos + dependencias, con precios del CSV."""
    finales, _, _ = cerrar_dependencias(config.MODULOS_BASE + modulos)
    precios = datos.precios()
    return [{"id": m, "nombre": precios[m]["nombre"], "precio": precios[m]["precio"]} for m in finales]


class ArgsGenerarConfiguracion(BaseModel):
    modulos: list[str] = Field(description="Ids de los módulos adicionales elegidos (sin los 3 base)")
    giro: str = Field(description="Giro del negocio")
    nombre_negocio: str = Field(default="Mi negocio", description="Nombre de ejemplo para la maqueta")


def generar_configuracion(args: ArgsGenerarConfiguracion) -> dict:
    catalogo = datos.modulos()
    finales, _, no_existen = cerrar_dependencias(config.MODULOS_BASE + args.modulos)
    if no_existen:
        return {"error": f"Módulos inexistentes: {no_existen}"}
    configuracion = {"negocio": args.nombre_negocio, "giro": args.giro,
                     "modulos": [{"id": m, "nombre": catalogo[m]["nombre"], "activo": True} for m in finales]}
    carpeta = _carpeta()
    ruta_json = carpeta / "config.json"
    ruta_json.write_text(json.dumps(configuracion, ensure_ascii=False, indent=2), encoding="utf-8")
    menu = "".join(f"<li>{html.escape(catalogo[m]['nombre'])}</li>" for m in finales)
    secciones = "".join(
        f"<section><h2>{html.escape(catalogo[m]['nombre'])}</h2><p>{html.escape(catalogo[m]['descripcion'])}</p>"
        f"<p><em>Datos de ejemplo.</em></p></section>" for m in finales)
    ruta_html = carpeta / "maqueta.html"
    ruta_html.write_text(
        f"<!DOCTYPE html><html lang='es'><meta charset='utf-8'><title>{html.escape(args.nombre_negocio)}</title>"
        f"<body><header><h1>{html.escape(args.nombre_negocio)}</h1><nav><ul>{menu}</ul></nav></header>"
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
