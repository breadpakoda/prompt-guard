"""
Alias module for classifier.py.
Provides is_danger, PredictionResult, and load_model.
"""
from .classifier import is_danger, PredictionResult, load_model

__all__ = ["is_danger", "PredictionResult", "load_model"]

