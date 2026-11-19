"""Coarse search: where in the Atlantic is the sea farthest from land?

This is the step before solve.py. It answers "which basin", not "where exactly": distances are spherical, the
coastline is GSHHG alone, the grid is a quarter of a degree.

Sea without a land mask: a cell is open water if it is more than 30 km from every coastline vertex and can be
reached, cell by cell, from a point in mid-Atlantic. The coast itself is the wall: the strip within 30 km of
it is wider than a cell, so no path crosses from the sea to the inland side. The Atlantic ends at 66.5 N,
60 S, 20 E south of Africa and 68 W south of America.
"""
import numpy as np
from scipy import ndimage
from scipy.spatial import cKDTree

from . import gshhg

STEP = 0.25
WEST, EAST, SOUTH, NORTH = -100.0, 20.0, -60.0, 66.5
SEED = (0.0, -30.0)  # lat, lon: mid-Atlantic on the equator
COAST_KM = 30.0
EARTH_KM = 6371.0088


def xyz(lat, lon):
    la, lo = np.radians(lat), np.radians(lon)
    return np.column_stack([np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)])


def search(gshhg_path):
    """The Atlantic's local maxima of distance from land, farthest first: [{'lat', 'lon', 'km'}]."""
    vlat, vlon = gshhg.vertices(gshhg_path)
    near = (vlon > WEST - 40) & (vlon < EAST + 40)  # land farther east or west cannot be the nearest
    tree = cKDTree(xyz(vlat[near], vlon[near]))

    lon = np.arange(WEST + STEP / 2, EAST, STEP)
    lat = np.arange(SOUTH + STEP / 2, NORTH, STEP)
    LO, LA = np.meshgrid(lon, lat)
    chord, _ = tree.query(xyz(LA.ravel(), LO.ravel()))
    km = (2 * np.arcsin(np.minimum(chord / 2, 1)) * EARTH_KM).reshape(LA.shape)

    water = km > COAST_KM
    water[(LA < -52) & (np.abs(LO + 68) < STEP)] = False  # Atlantic | Pacific south of Cape Horn
    labels, _ = ndimage.label(water)
    atlantic = labels == labels[int((SEED[0] - SOUTH) / STEP), int((SEED[1] - WEST) / STEP)]

    field = np.where(atlantic, km, 0)
    peaks = (field == ndimage.maximum_filter(field, size=int(10 / STEP))) & (field > 1000)  # one per 10 degrees
    return sorted(({"lat": float(LA[i, j]), "lon": float(LO[i, j]), "km": round(float(km[i, j]), 1)}
                   for i, j in zip(*np.nonzero(peaks))), key=lambda p: -p["km"])
