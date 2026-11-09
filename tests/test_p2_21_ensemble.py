"""Contrato y ejecución reproducible de 2.1 con tarjetas sintéticas."""
import ast
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from threadpoolctl import threadpool_limits

from scripts import entrenar_p2_21_ensemble as ensemble


def fixture():
    rng = np.random.default_rng(31)
    size = 120
    features = rng.normal(size=(size, len(ensemble.FEATURES)))
    target = (features[:, 4] + rng.normal(size=size) > 0.5).astype(int)
    data = pd.DataFrame(features, columns=ensemble.FEATURES)
    data["operador"] = np.resize(["Transmetro", "Aerometro", "Transurbano", "MetroRiel"], size)
    data["unidad_id"] = [f"{i:04d}" for i in range(size)]
    data["corte"] = "A"
    data["fecha_corte"] = "2026-07-01"
    data["etiqueta"] = target
    return data


class EnsembleTest(unittest.TestCase):
    def test_mismos_predictores_de_14_y_solo_predictores_en_pipeline(self):
        historical = ast.parse((ensemble.ROOT / "scripts/entrenar_fase1_14.py").read_text(encoding="utf-8"))
        columns = {}
        for node in historical.body:
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                name = node.targets[0].id
                if name in {"num_cols", "cat_cols"}:
                    columns[name] = ast.literal_eval(node.value)
        self.assertEqual(list(ensemble.PREDICTORS), columns["num_cols"] + columns["cat_cols"])
        for name in ("logistica_l1", "logistica_l2", "rf_somero"):
            pipe = ensemble.build_model(ensemble.MODELS[name])
            actual = [column for _, _, group in pipe.named_steps["prep"].transformers for column in group]
            self.assertEqual(actual, list(ensemble.PREDICTORS))

    def test_sql_selecciona_solo_a_de_la_fecha_correcta(self):
        # Sólo se adapta la notación del literal timestamp de PostgreSQL.
        valid = fixture().iloc[:1]
        cases = pd.concat([
            valid, valid.assign(corte="B", fecha_corte="2026-07-31", etiqueta=1),
            valid.assign(corte="C", fecha_corte="2026-08-30", etiqueta=None),
            valid.assign(fecha_corte="2026-07-02"),
        ])
        query = ensemble.QUERY.replace("timestamp '2026-07-01 00:00:00'", "'2026-07-01'")
        with closing(sqlite3.connect(":memory:")) as conn:
            conn.execute("attach database ':memory:' as silver")
            names = ", ".join(ensemble.INPUT_COLUMNS)
            conn.execute(f"create table silver.silver_p2_features_tarjeta ({names})")
            marks = ", ".join("?" for _ in ensemble.INPUT_COLUMNS)
            conn.executemany(f"insert into silver.silver_p2_features_tarjeta ({names}) values ({marks})",
                             cases[list(ensemble.INPUT_COLUMNS)].itertuples(index=False, name=None))
            self.assertEqual(conn.execute(query).fetchall(), list(valid[list(ensemble.INPUT_COLUMNS)]
                                                                   .itertuples(index=False, name=None)))

    def test_rechaza_b_c_fecha_incorrecta_nulos_y_duplicados(self):
        data = fixture()
        for invalid in (data.assign(corte="B"), data.assign(corte="C"),
                        data.assign(fecha_corte="2026-07-02"), data.assign(etiqueta=None),
                        pd.concat([data, data.iloc[:1]]), data.assign(unidad_id=None)):
            with self.assertRaises(ValueError):
                ensemble.prepare_cut_a(invalid)

    def test_recuperacion_limita_poblacion_a_y_rechaza_una_huella_distinta(self):
        conn = MagicMock()
        conn.__enter__.return_value = conn
        conn.execute.return_value.fetchall.return_value = fixture().to_dict(orient="records")
        with patch.object(ensemble, "connect", return_value=conn):
            with self.assertRaisesRegex(ValueError, "huella publicada"):
                ensemble.load_cut_a(recalculate=True)
        readonly, select = conn.execute.call_args_list
        self.assertEqual(readonly.args, ("set transaction read only",))
        query, = select.args
        population = query.split("usos_validos AS", 1)[0]
        self.assertIn("poblacion_a AS MATERIALIZED", population)
        self.assertIn("WHERE corte = 'A' AND fecha_corte = timestamp '2026-07-01 00:00:00'", population)
        self.assertEqual(query.count("silver.silver_p2_poblacion_tarjeta"), 1)

    def test_folds_estables_estratificados_y_validacion_disjunta(self):
        data = ensemble.prepare_cut_a(fixture())
        shuffled = ensemble.prepare_cut_a(fixture().sample(frac=1, random_state=42))
        pd.testing.assert_frame_equal(data, shuffled)
        y = data.etiqueta.to_numpy()
        folds = ensemble.make_folds(y)
        self.assertEqual(len(folds), 5)
        for train, valid in folds:
            self.assertEqual(len(set(train) & set(valid)), 0)
            self.assertEqual(len(train) + len(valid), len(y))
            self.assertLessEqual(abs(int(y[valid].sum()) - y.sum() / 5), 1)
        np.testing.assert_array_equal(np.sort(np.concatenate([v for _, v in folds])), np.arange(len(y)))

    def test_experimento_reproducible_y_csv_oof_procede_del_estimador_de_su_fold(self):
        data = fixture()
        first, oof = ensemble.run_experiment(data)
        second, repeated = ensemble.run_experiment(data.sample(frac=1, random_state=88))
        self.assertEqual(first, second)
        pd.testing.assert_frame_equal(oof, repeated)
        self.assertEqual(set(oof.corte), {"A"})
        self.assertEqual(set(oof.fold), set(range(5)))
        self.assertTrue(oof.unidad_id.is_unique)
        self.assertEqual(first["modelos"]["baseline_tasa"]["auc_validacion"]["media"], 0.5)
        self.assertEqual({row["variable"] for row in first["importancia"]["variables"]}, set(ensemble.PREDICTORS))
        prepared = ensemble.prepare_cut_a(data)
        X = prepared[list(ensemble.PREDICTORS)]
        y = prepared.etiqueta.to_numpy()
        with threadpool_limits(limits=1):
            for fold, (train, valid) in enumerate(ensemble.make_folds(y)):
                model = ensemble.build_model(first["recomendado"]["configuracion"])
                model.fit(X.iloc[train], y[train])
                saved = oof.loc[oof.fold.eq(fold), "probabilidad_abandono"].to_numpy()
                np.testing.assert_array_equal(saved, model.predict_proba(X.iloc[valid])[:, 1])
                self.assertEqual(roc_auc_score(y[valid], saved),
                                 first["modelos"][first["recomendado"]["modelo"]]["folds"][fold]["auc_validacion"])
        temporary_root = ensemble.ROOT / "datos_red"
        temporary_root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as tmp:
            path = Path(tmp) / "oof.csv"
            ensemble.write_text(path, oof.to_csv(index=False, float_format="%.17g", lineterminator="\n"))
            loaded = pd.read_csv(path, dtype={"unidad_id": str}, parse_dates=["fecha_corte"],
                                 float_precision="round_trip")
            pd.testing.assert_frame_equal(loaded, oof)
            self.assertEqual(json.loads(loaded.configuracion_modelo.iloc[0]), first["recomendado"]["configuracion"])

    def test_importancia_del_bosque_solo_en_submuestra_de_validacion(self):
        data = ensemble.prepare_cut_a(fixture())
        X, y = data[list(ensemble.PREDICTORS)], data.etiqueta.to_numpy()
        folds = ensemble.make_folds(y)
        spec = ensemble.MODELS["rf_somero"]
        oof = np.empty(len(y))
        with threadpool_limits(limits=1):
            for train, valid in folds:
                model = ensemble.build_model(spec).fit(X.iloc[train], y[train])
                oof[valid] = model.predict_proba(X.iloc[valid])[:, 1]
            real_importance = ensemble.permutation_importance
            seen = []

            def record(model, features, target, **kwargs):
                fold = len(seen)
                train, valid = folds[fold]
                seen.append(fold)
                self.assertLessEqual(set(features.index), set(valid))
                self.assertFalse(set(features.index) & set(train))
                self.assertEqual(len(features), 12)
                self.assertEqual(list(features.columns), list(ensemble.PREDICTORS))
                self.assertEqual(set(target), {0, 1})
                self.assertEqual(kwargs["scoring"], "roc_auc")
                self.assertEqual(kwargs["n_repeats"], 5)
                self.assertEqual(kwargs["random_state"], 2026 + fold)
                return real_importance(model, features, target, **kwargs)

            with patch.object(ensemble, "RF_IMPORTANCE_LIMIT", 12), patch.object(ensemble, "permutation_importance", record):
                report = ensemble.validation_importance(spec, X, y, folds, oof)
        self.assertEqual(seen, list(range(5)))
        self.assertTrue(all(r["muestra"] == 12 for r in report["muestras"]))


if __name__ == "__main__":
    unittest.main()
