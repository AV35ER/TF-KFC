"""Transpilación del AST aceptado a SQL demostrativo, sin ejecutar consultas."""

import re

from automatas import PAGOS, PRODUCTOS
from semantico import CANTIDAD_MAX, CANTIDAD_MIN


_CANTIDAD_ASCII = re.compile(r"[0-9]+", re.ASCII)


class ErrorTraduccion(ValueError):
    """El árbol o sus datos no cumplen el contrato seguro de traducción."""


def _forma(nodo, simbolo, cantidad_hijos=None):
    if not isinstance(nodo, dict) or nodo.get("simbolo") != simbolo:
        raise ErrorTraduccion(f"Se esperaba el símbolo {simbolo} en el AST.")
    hijos = nodo.get("hijos")
    if not isinstance(hijos, list) or (cantidad_hijos is not None and len(hijos) != cantidad_hijos):
        raise ErrorTraduccion(f"El nodo {simbolo} tiene una estructura inesperada.")
    return hijos


def _lexema(nodo, simbolo):
    _forma(nodo, simbolo, 0)
    if not isinstance(nodo.get("lexema"), str):
        raise ErrorTraduccion(f"El terminal {simbolo} no contiene un lexema válido.")
    return nodo["lexema"]


def _extraer_items(nodo):
    hijos = _forma(nodo, "ITEMS")
    if len(hijos) == 1:
        item = _forma(hijos[0], "ITEM", 2)
        return [(_lexema(item[0], "producto"), _lexema(item[1], "cantidad"))]
    if len(hijos) == 2:
        anterior = _extraer_items(hijos[0])
        item = _forma(hijos[1], "ITEM", 2)
        return anterior + [(_lexema(item[0], "producto"), _lexema(item[1], "cantidad"))]
    raise ErrorTraduccion("La producción ITEMS no coincide con la gramática del analizador.")


def resumen_ast(arbol):
    """Resume los símbolos/lexemas en el orden del árbol, no desde el DSL original."""
    if not isinstance(arbol, dict):
        return "Árbol sintáctico no disponible."
    simbolos = []

    def recorrer(nodo):
        simbolos.append(nodo.get("simbolo", "?"))
        for hijo in nodo.get("hijos", []):
            recorrer(hijo)

    recorrer(arbol)
    return " -> ".join(simbolos)


def traducir(arbol, semantico):
    """Genera SQL solo desde un AST válido y datos semánticos ya aprobados."""
    if not isinstance(semantico, dict) or not semantico.get("valida"):
        raise ErrorTraduccion("El pedido no superó la validación semántica.")

    # El parser expone PEDIDO como raíz; se admite también un wrapper S' si
    # una representación futura incluye explícitamente la producción aumentada.
    if not isinstance(arbol, dict):
        raise ErrorTraduccion("El AST debe ser un objeto de nodos.")
    pedido = _forma(arbol, "S'", 1)[0] if arbol.get("simbolo") == "S'" else arbol
    hijos_pedido = _forma(pedido, "PEDIDO", 2)
    items_ast = _extraer_items(hijos_pedido[0])
    pago = _lexema(hijos_pedido[1], "pago")

    if pago not in PAGOS:
        raise ErrorTraduccion("El medio de pago no pertenece a la lista permitida.")
    if not items_ast:
        raise ErrorTraduccion("El pedido no contiene productos.")

    items = []
    vistos = set()
    for producto, cantidad_texto in items_ast:
        if producto not in PRODUCTOS:
            raise ErrorTraduccion("El producto no pertenece a la lista permitida.")
        if not _CANTIDAD_ASCII.fullmatch(cantidad_texto):
            raise ErrorTraduccion("La cantidad debe contener exclusivamente dígitos ASCII.")
        cantidad = int(cantidad_texto)
        if not CANTIDAD_MIN <= cantidad <= CANTIDAD_MAX:
            raise ErrorTraduccion("La cantidad incumple la regla semántica R1.")
        if producto in vistos:
            raise ErrorTraduccion("El producto incumple la regla semántica R2.")
        vistos.add(producto)
        items.append((producto, cantidad))

    items_semanticos = semantico.get("items")
    if items_semanticos != items or semantico.get("pago") != pago:
        raise ErrorTraduccion("El AST no coincide con los datos del análisis semántico.")

    detalle = ",\n".join(
        f"(:pedido_id, '{producto}', {cantidad})" for producto, cantidad in items
    )
    sql = (
        "INSERT INTO pedidos (id, medio_pago)\n"
        f"VALUES (:pedido_id, '{pago}');\n\n"
        "INSERT INTO detalle_pedido (pedido_id, producto, cantidad)\n"
        f"VALUES\n{detalle};"
    )
    return {
        "clasificacion": "Transpilador",
        "destino": "SQL",
        "sql": sql,
        "items": items,
        "pago": pago,
        "resumen_ast": resumen_ast(arbol),
    }
