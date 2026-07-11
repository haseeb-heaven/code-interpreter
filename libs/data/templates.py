# -*- coding: utf-8 -*-
"""Prompt templates for data / files / viz (Issue #222)."""

from __future__ import annotations

TEMPLATES = {
	"data": [
		'analyze [file.csv] and show me a summary of every column',
		'find all rows where [column] is null and show me patterns',
		'group by [category_column] and calculate mean of [value_column]',
		'find the top 10 [items] by [metric]',
		'detect outliers in [column] using IQR method',
		'clean the data: remove duplicates, fill nulls with median, fix date formats',
		'predict [target_column] using the other columns (linear regression)',
		'generate a full EDA report and save it as HTML',
	],
	"files": [
		'list all files in [folder] modified in the last 7 days',
		'rename all PDFs in [folder] with today\'s date prefix',
		'find duplicate files by content hash in [folder]',
		'convert all .xlsx files in [folder] to CSV',
	],
	"viz": [
		'plot the distribution of [column] as a histogram',
		'show me the correlation between [col1] and [col2]',
		'create a bar chart of [metric] by [category]',
		'draw a time series of [value] over [date_column]',
	],
}


def format_templates(category: str = "data") -> str:
	key = (category or "data").lower().strip()
	if key not in TEMPLATES:
		key = "data"
	title = {
		"data": "Data Analysis Templates",
		"files": "File Operation Templates",
		"viz": "Visualization Templates",
	}[key]
	lines = [f"{title} — copy and edit:", ""]
	for i, item in enumerate(TEMPLATES[key], 1):
		lines.append(f'  {i}. "{item}"')
	return "\n".join(lines)
