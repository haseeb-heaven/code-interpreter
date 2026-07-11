# -*- coding: utf-8 -*-
"""Lightweight ML shortcut runners (Issue #223)."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


def run_ml_shortcut(
	df: pd.DataFrame,
	kind: str,
	target: Optional[str] = None,
	n_clusters: int = 3,
) -> Tuple[str, Dict[str, Any]]:
	"""Run a small sklearn pipeline and return a text summary + metrics."""
	kind_l = (kind or "").lower().strip()
	if df is None or df.empty:
		raise ValueError("No dataframe loaded")

	try:
		import numpy as np
		from sklearn.compose import ColumnTransformer
		from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
		from sklearn.cluster import KMeans
		from sklearn.metrics import (
			accuracy_score,
			f1_score,
			mean_squared_error,
			r2_score,
		)
		from sklearn.model_selection import train_test_split
		from sklearn.pipeline import Pipeline
		from sklearn.preprocessing import OneHotEncoder, StandardScaler
	except ImportError as exc:
		raise ImportError(
			"scikit-learn is required for /ml shortcuts. Install with: pip install scikit-learn"
		) from exc

	rng = 42
	numeric = df.select_dtypes(include="number").columns.tolist()
	categorical = [c for c in df.columns if c not in numeric]

	if kind_l == "cluster":
		feats = df[numeric].dropna()
		if feats.empty:
			raise ValueError("Need numeric columns for clustering")
		model = KMeans(n_clusters=max(2, int(n_clusters)), random_state=rng, n_init=10)
		labels = model.fit_predict(StandardScaler().fit_transform(feats))
		metrics = {"n_clusters": int(n_clusters), "inertia": float(model.inertia_)}
		summary = (
			f"KMeans clustering complete. n={len(feats)} clusters={n_clusters} "
			f"inertia={model.inertia_:.4f}\n"
			f"Cluster sizes: {dict(zip(*np.unique(labels, return_counts=True)))}"
		)
		return summary, metrics

	if not target or target not in df.columns:
		raise ValueError(f"Target column required / not found: {target!r}")

	y = df[target]
	X = df.drop(columns=[target])
	num_cols = X.select_dtypes(include="number").columns.tolist()
	cat_cols = [c for c in X.columns if c not in num_cols]
	pre = ColumnTransformer(
		transformers=[
			("num", StandardScaler(), num_cols),
			("cat", OneHotEncoder(handle_unknown="ignore"), cat_cols),
		],
		remainder="drop",
	)

	if kind_l == "classify":
		model = RandomForestClassifier(random_state=rng)
		X_train, X_test, y_train, y_test = train_test_split(
			X, y, test_size=0.2, random_state=rng
		)
		pipe = Pipeline([("pre", pre), ("model", model)])
		pipe.fit(X_train, y_train)
		pred = pipe.predict(X_test)
		acc = float(accuracy_score(y_test, pred))
		f1 = float(f1_score(y_test, pred, average="weighted"))
		metrics = {"accuracy": acc, "f1_weighted": f1, "n_test": len(y_test)}
		summary = f"Classifier trained on '{target}'. accuracy={acc:.4f} f1_weighted={f1:.4f}"
		return summary, metrics

	if kind_l == "regress":
		model = RandomForestRegressor(random_state=rng)
		X_train, X_test, y_train, y_test = train_test_split(
			X, y, test_size=0.2, random_state=rng
		)
		pipe = Pipeline([("pre", pre), ("model", model)])
		pipe.fit(X_train, y_train)
		pred = pipe.predict(X_test)
		r2 = float(r2_score(y_test, pred))
		rmse = float(mean_squared_error(y_test, pred) ** 0.5)
		metrics = {"r2": r2, "rmse": rmse, "n_test": len(y_test)}
		summary = f"Regressor trained on '{target}'. R2={r2:.4f} RMSE={rmse:.4f}"
		return summary, metrics

	raise ValueError("Usage: /ml classify|regress|cluster [target_or_n]")
