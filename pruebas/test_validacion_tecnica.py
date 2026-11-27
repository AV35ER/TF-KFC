"""Pruebas de regresión para AFD, integración Flask y exportación JFLAP."""
import re
import unittest
import xml.etree.ElementTree as ET
from io import BytesIO

import automatas
import app as aplicacion
import semantico
import sintactico


class ValidacionAFD(unittest.TestCase):
    def test_afd_de_cada_token_y_equivalencia_regex(self):
        for token in automatas.TOKENS:
            nombre = token["token"]
            _, _, afd = automatas.automatas_token(nombre)
            patron = re.compile(token["er"] + r"\Z")
            candidatos = token["lexemas"] + ["", "X", "-2", "2.5", "١", "²"]
            for cadena in candidatos:
                with self.subTest(token=nombre, cadena=cadena):
                    self.assertEqual(automatas.reconoce_afd(cadena, afd),
                                     patron.fullmatch(cadena) is not None)

    def test_cantidades_solo_ascii(self):
        _, _, afd = automatas.automatas_token("CANTIDAD")
        for cadena in ("1", "12", "50", "0", "51"):
            with self.subTest(cadena=cadena):
                self.assertTrue(automatas.reconoce_afd(cadena, afd))
        for cadena in ("١", "²", "-2", "2.5", "", "DOS"):
            with self.subTest(cadena=cadena):
                self.assertFalse(automatas.reconoce_afd(cadena, afd))
                self.assertEqual(automatas.clasificar(cadena), "DESCONOCIDO")

    def test_cache_no_comparte_objetos_mutables(self):
        t1, afnd1, afd1 = automatas.automatas_token("CANTIDAD")
        referencia = automatas.automatas_token("CANTIDAD")
        t1["er"] = "CORRUPTA"
        afnd1["trans"].clear()
        afd1["trans"].clear()
        t2, afnd2, afd2 = automatas.automatas_token("CANTIDAD")
        self.assertEqual(t2["er"], "[0-9]+")
        self.assertTrue(afnd2["trans"])
        self.assertTrue(afd2["trans"])
        self.assertEqual(referencia[2]["trans"], afd2["trans"])


class IntegracionCompilador(unittest.TestCase):
    def setUp(self):
        self.client = aplicacion.app.test_client()

    def pedido(self, texto):
        respuesta = self.client.post("/api/analizar", json={"texto": texto})
        self.assertEqual(respuesta.status_code, 200)
        return respuesta.get_json()["pedidos"][0]

    def test_pedidos_validos_limites_y_arbol(self):
        for texto in ("POLLO 1 EFECTIVO", "POLLO 50 YAPE", "ALITAS 12 TARJETA"):
            with self.subTest(texto=texto):
                p = self.pedido(texto)
                self.assertTrue(p["valida"])
                detalle = aplicacion.analizar_texto(texto)[2][0]
                self.assertIn("digraph Arbol", detalle["dot_arbol"])
                self.assertTrue(detalle["derivacion"])

    def test_rechazos_por_etapa_y_bloqueo_de_etapas_posteriores(self):
        casos = [("PIZZA 2 EFECTIVO", "léxica"), ("POLLO ١ EFECTIVO", "léxica"),
                 ("POLLO ² EFECTIVO", "léxica"), ("POLLO EFECTIVO", "sintáctica"),
                 ("POLLO 0 EFECTIVO", "semántica"), ("POLLO 51 EFECTIVO", "semántica"),
                 ("POLLO 2 POLLO 3 EFECTIVO", "semántica")]
        for texto, fase in casos:
            with self.subTest(texto=texto):
                p = self.pedido(texto)
                self.assertFalse(p["valida"])
                self.assertEqual(p["fase"], fase)
                detalle = aplicacion.analizar_texto(texto)[2][0]
                if fase == "léxica":
                    self.assertFalse(detalle["sintaxis_ok"])
                    self.assertIsNone(detalle["semantico"])
                elif fase == "sintáctica":
                    self.assertFalse(detalle["sintaxis_ok"])
                    self.assertIsNone(detalle["semantico"])
                else:
                    self.assertTrue(detalle["sintaxis_ok"])
                    self.assertFalse(detalle["semantico"]["valida"])

    def test_multiples_pedidos_independientes_y_archivo_txt(self):
        data = {"texto": "POLLO 1 EFECTIVO\nPOLLO 0 EFECTIVO\nALITAS 2 YAPE"}
        resp = self.client.post("/api/analizar", json=data).get_json()
        self.assertEqual([p["valida"] for p in resp["pedidos"]], [True, False, True])
        archivo = {"archivo": (BytesIO(b"POLLO 1 EFECTIVO\n"), "pedidos.txt")}
        pagina = self.client.post("/", data=archivo, content_type="multipart/form-data")
        self.assertEqual(pagina.status_code, 200)
        self.assertIn(b"POLLO 1 EFECTIVO", pagina.data)

    def test_vacio_y_carga_de_pagina(self):
        self.assertEqual(self.client.post("/api/analizar", json={"texto": " "}).status_code, 400)
        pagina = self.client.get("/")
        self.assertEqual(pagina.status_code, 200)
        self.assertIn(b'name="viewport"', pagina.data)
        procesada = self.client.post("/", data={"texto": "POLLO 1 EFECTIVO"})
        self.assertEqual(procesada.status_code, 200)
        self.assertIn(b"data-dot", procesada.data)

    def test_descargas_de_ejemplo_y_exportaciones(self):
        ejemplo = self.client.get("/ejemplo.txt")
        self.assertEqual(ejemplo.status_code, 200)
        self.assertIn(b"POLLO", ejemplo.data)
        for token in ("PRODUCTO", "CANTIDAD", "PAGO"):
            for tipo in ("afnd", "afd"):
                with self.subTest(token=token, tipo=tipo):
                    descarga = self.client.get(f"/jflap/{token}_{tipo}.jff")
                    self.assertEqual(descarga.status_code, 200)
                    self.assertIn("attachment", descarga.headers["Content-Disposition"])


class RegresionYJFLAP(unittest.TestCase):
    def test_vocabulario_gramatica_y_reglas_conservados(self):
        self.assertEqual(automatas.LISTA_PRODUCTOS, ["POLLO", "ALITAS", "HAMBURGUESA", "PAPAS", "GASEOSA", "COMBO", "NUGGETS", "ENSALADA", "HELADO", "POPCORN"])
        self.assertEqual(automatas.LISTA_PAGOS, ["EFECTIVO", "TARJETA", "YAPE", "PLIN"])
        self.assertEqual(sintactico.PRODUCCIONES, [("S'", ["PEDIDO"]), ("PEDIDO", ["ITEMS", "pago"]), ("ITEMS", ["ITEMS", "ITEM"]), ("ITEMS", ["ITEM"]), ("ITEM", ["producto", "cantidad"])])
        self.assertEqual(semantico.CANTIDAD_MIN, 1)
        self.assertEqual(semantico.CANTIDAD_MAX, 50)

    def test_tablas_y_graficos_de_transicion_coherentes(self):
        for token in automatas.TOKENS:
            nombre = token["token"]
            _, afnd, afd = automatas.automatas_token(nombre)
            filas = automatas.tabla_afd(afd)
            self.assertEqual(len(filas), len(afd["estados"]))
            self.assertEqual({f["estado"] for f in filas}, set(afd["estados"]))
            for (origen, simbolo), destino in afd["trans"].items():
                self.assertIn(origen, afd["estados"])
                self.assertIn(destino, afd["estados"])
                self.assertIn(simbolo, afd["alfabeto"])
            self.assertIn("digraph AFND", automatas.dot_afnd(afnd))
            self.assertIn("digraph AFD", automatas.dot_afd(afd))
        cols_a, cols_g, filas = sintactico.tabla_lr()
        self.assertEqual(len(filas), len(sintactico.ESTADOS))
        self.assertEqual(len(filas[0]["accion"]), len(cols_a))
        self.assertEqual(len(filas[0]["ir_a"]), len(cols_g))

    def simular_jff(self, root, cadena):
        estados = {s.attrib["id"]: s for s in root.findall("./automaton/state")}
        inicial = next(i for i, s in estados.items() if s.find("initial") is not None)
        finales = {i for i, s in estados.items() if s.find("final") is not None}
        trans = root.findall("./automaton/transition")
        alcanzables = {inicial}
        for _ in range(len(cadena) + 1):
            nuevos = set(alcanzables)
            cambio = True
            while cambio:
                cambio = False
                for tr in trans:
                    leer = tr.findtext("read") or ""
                    if tr.findtext("from") in nuevos and not leer and tr.findtext("to") not in nuevos:
                        nuevos.add(tr.findtext("to")); cambio = True
            alcanzables = nuevos
            if not cadena:
                break
            simbolo, cadena = cadena[0], cadena[1:]
            alcanzables = {tr.findtext("to") for tr in trans
                           if tr.findtext("from") in alcanzables
                           and (tr.findtext("read") or "") in (simbolo, "[0-9]" if simbolo in "0123456789" else "\0")}
        cambio = True
        while cambio:
            cambio = False
            for tr in trans:
                if tr.findtext("from") in alcanzables and not (tr.findtext("read") or "") and tr.findtext("to") not in alcanzables:
                    alcanzables.add(tr.findtext("to")); cambio = True
        return bool(alcanzables & finales)

    def test_seis_exportaciones_jff_y_reconocimiento(self):
        ejemplos = {"PRODUCTO": ("POLLO", "PIZZA"), "CANTIDAD": ("12", "١"), "PAGO": ("YAPE", "BITCOIN")}
        client = aplicacion.app.test_client()
        for token, (acepta, rechaza) in ejemplos.items():
            for tipo in ("afnd", "afd"):
                with self.subTest(token=token, tipo=tipo):
                    contenido = automatas.a_jflap(token, tipo)
                    root = ET.fromstring(contenido)
                    self.assertEqual(root.findtext("type"), "fa")
                    estados = root.findall("./automaton/state")
                    trans = root.findall("./automaton/transition")
                    self.assertTrue(estados)
                    self.assertTrue(trans)
                    self.assertEqual(sum(s.find("initial") is not None for s in estados), 1)
                    self.assertTrue(any(s.find("final") is not None for s in estados))
                    self.assertTrue(self.simular_jff(root, acepta))
                    self.assertFalse(self.simular_jff(root, rechaza))
                    respuesta = client.get(f"/jflap/{token}_{tipo}.jff")
                    self.assertEqual(respuesta.status_code, 200)
                    self.assertEqual(ET.fromstring(respuesta.data).tag, "structure")
                    self.assertIn("digraph", automatas.dot_afnd(automatas.automatas_token(token)[1]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
