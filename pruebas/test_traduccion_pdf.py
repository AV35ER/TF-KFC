import unittest
from io import BytesIO
from unittest.mock import patch

from pypdf import PdfReader

import app
import traductor


class TranspilacionDsl(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def analizar(self, texto):
        return app.analizar_texto(texto)[2]

    def test_casos_obligatorios_y_sql_derivado_del_ast(self):
        casos = (
            ("POLLO 2 EFECTIVO", True, "VALUES (:pedido_id, 'EFECTIVO');"),
            ("POLLO 2 PAPAS 1 EFECTIVO", True, "(:pedido_id, 'PAPAS', 1)"),
            ("POLLO 0 EFECTIVO", False, "R1"),
            ("POLLO 51 EFECTIVO", False, "R1"),
            ("POLLO 2 POLLO 1 EFECTIVO", False, "R2"),
            ("PIZZA 2 EFECTIVO", False, "l"),
            ("POLLO EFECTIVO", False, "Error sintáctico"),
        )
        for texto, debe_generar, evidencia in casos:
            with self.subTest(texto=texto):
                pedido = self.analizar(texto)[0]
                self.assertEqual(bool(pedido["traduccion"]["sql"]), debe_generar)
                if debe_generar:
                    self.assertIn(evidencia, pedido["traduccion"]["sql"])
                    self.assertTrue(pedido["traduccion"]["generada"])
                else:
                    self.assertFalse(pedido["traduccion"]["generada"])
                    self.assertEqual(pedido["traduccion"]["sql"], "")
                    self.assertIn(evidencia, pedido["traduccion"]["motivo"] + pedido["error"])

    def test_ast_preserva_pares_orden_pago_y_cantidad(self):
        pedido = self.analizar("POLLO 2 PAPAS 1 YAPE")[0]
        traduccion = pedido["traduccion"]
        self.assertEqual(traduccion["items"], [("POLLO", 2), ("PAPAS", 1)])
        self.assertEqual(traduccion["pago"], "YAPE")
        self.assertLess(traduccion["sql"].index("'POLLO', 2"), traduccion["sql"].index("'PAPAS', 1"))
        self.assertIn("producto", traduccion["resumen_ast"])

    def test_arbol_inconsistente_o_datos_fuera_de_lista_no_se_traducen(self):
        pedido = self.analizar("POLLO 2 EFECTIVO")[0]
        arbol = pedido["arbol"]
        sem = pedido["semantico"]
        arbol_modificado = {
            "simbolo": "PEDIDO",
            "hijos": [
                {"simbolo": "ITEMS", "hijos": [
                    {"simbolo": "ITEM", "hijos": [
                        {"simbolo": "producto", "lexema": "POLLO", "hijos": []},
                        {"simbolo": "cantidad", "lexema": "2", "hijos": []},
                    ]}
                ]},
                {"simbolo": "pago", "lexema": "EFECTIVO'; DROP TABLE pedidos;--", "hijos": []},
            ],
        }
        with self.assertRaises(traductor.ErrorTraduccion):
            traductor.traducir(arbol_modificado, sem)
        sem_modificado = {**sem, "items": [("POLLO", 3)]}
        with self.assertRaises(traductor.ErrorTraduccion):
            traductor.traducir(arbol, sem_modificado)

    def test_pedidos_multiples_son_independientes(self):
        pedidos = self.analizar("POLLO 1 EFECTIVO\nPAPAS 2 YAPE\nPOLLO 0 PLIN")
        self.assertEqual([p["traduccion"]["generada"] for p in pedidos], [True, True, False])
        self.assertIn("'EFECTIVO'", pedidos[0]["traduccion"]["sql"])
        self.assertNotIn("PAPAS", pedidos[0]["traduccion"]["sql"])
        self.assertIn("'YAPE'", pedidos[1]["traduccion"]["sql"])
        self.assertNotIn("POLLO", pedidos[1]["traduccion"]["sql"])

    def test_traduccion_no_ejecuta_sql(self):
        pedido = self.analizar("POLLO 2 EFECTIVO")[0]
        self.assertTrue(pedido["traduccion"]["sql"].startswith("INSERT INTO pedidos"))
        self.assertFalse(hasattr(app.app, "db"))
        self.assertFalse(any(rule.rule in ("/execute-sql", "/database") for rule in app.app.url_map.iter_rules()))


class ReportePdf(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_descarga_pdf_a4_integro_con_contenido_y_pedido_rechazado(self):
        texto = "POLLO 2 PAPAS 1 EFECTIVO\nPIZZA 2 EFECTIVO"
        response = self.client.post("/reporte-traduccion.pdf", data={"texto": texto})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/pdf")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertTrue(response.data.startswith(b"%PDF-"))

        reader = PdfReader(BytesIO(response.data))
        self.assertGreaterEqual(len(reader.pages), 1)
        self.assertAlmostEqual(float(reader.pages[0].mediabox.width), 595.276, delta=1)
        self.assertAlmostEqual(float(reader.pages[0].mediabox.height), 841.89, delta=1)
        contenido = "\n".join(page.extract_text() or "" for page in reader.pages)
        for requerido in (
            "Reporte de traducción del DSL", "POLLO 2 PAPAS 1 EFECTIVO",
            "PIZZA 2 EFECTIVO", "PRODUCTO(POLLO)", "Análisis léxico",
            "Análisis sintáctico", "Análisis semántico", "Gramática aplicada",
            "Transpilador", "SQL", "INSERT INTO pedidos", "Traducción no generada",
            "Fase del error", "Página 1", "No se ejecuta contra una",
        ):
            self.assertIn(requerido, contenido)
        self.assertIn("INSERT INTO detalle_pedido", contenido)
        self.assertIn("SQL: no generado.", contenido)
        # El bloque del pedido rechazado no contiene un INSERT generado para PIZZA.
        bloque_rechazado = contenido.split("Pedido de la línea 2", 1)[1]
        self.assertNotIn("INSERT INTO pedidos", bloque_rechazado)
        self.assertNotIn("PIZZA', 2", bloque_rechazado)

    def test_reporte_multipedido_y_errores_de_entrada(self):
        response = self.client.post("/reporte-traduccion.pdf", data={
            "texto": "POLLO 1 EFECTIVO\nPOLLO 51 TARJETA\nPOLLO EFECTIVO",
        })
        self.assertEqual(response.status_code, 200)
        contenido = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(response.data)).pages)
        self.assertIn("Pedido de la línea 1", contenido)
        self.assertIn("Pedido de la línea 2", contenido)
        self.assertIn("Pedido de la línea 3", contenido)
        self.assertIn("R1", contenido)
        self.assertIn("sintáctica", contenido)
        self.assertEqual(self.client.post("/reporte-traduccion.pdf", data={"texto": ""}).status_code, 400)
        response_utf8 = self.client.post(
            "/reporte-traduccion.pdf",
            data={"archivo": (BytesIO(b"\xff"), "pedido.txt")},
            content_type="multipart/form-data",
        )
        self.assertEqual(response_utf8.status_code, 400)

    def test_generador_pdf_no_llama_al_ejecutor_sql(self):
        with patch.object(traductor, "traducir", wraps=traductor.traducir) as traducir_mock:
            response = self.client.post("/reporte-traduccion.pdf", data={"texto": "POLLO 2 EFECTIVO"})
        self.assertEqual(response.status_code, 200)
        traducir_mock.assert_called_once()
        self.assertTrue(response.data.startswith(b"%PDF-"))


if __name__ == "__main__":
    unittest.main()
