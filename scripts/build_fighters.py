"""Build original skinned humanoid GLBs with authored combat animation clips.
No downloaded assets or runtime geometry stand-ins. CC0; reproducible stdlib pipeline.
Geometry is modelled as shaped cross sections, faceted cloth and sculpted hair.
"""

import json
import math
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BONES = [
    ("Root", -1, (0, 0, 0)),
    ("Hips", 0, (0, 1.0, 0)),
    ("Spine", 1, (0, 1.3, 0)),
    ("Chest", 2, (0, 1.7, 0)),
    ("Neck", 3, (0, 2.01, 0)),
    ("Head", 4, (0, 2.17, 0)),
    ("ArmL", 3, (-0.39, 1.87, 0)),
    ("ForeL", 6, (-0.53, 1.48, 0)),
    ("HandL", 7, (-0.58, 1.13, 0.02)),
    ("ArmR", 3, (0.39, 1.87, 0)),
    ("ForeR", 9, (0.53, 1.48, 0)),
    ("HandR", 10, (0.58, 1.13, 0.02)),
    ("ThighL", 1, (-0.18, 0.99, 0)),
    ("ShinL", 12, (-0.19, 0.54, 0)),
    ("FootL", 13, (-0.19, 0.10, 0.02)),
    ("ThighR", 1, (0.18, 0.99, 0)),
    ("ShinR", 15, (0.19, 0.54, 0)),
    ("FootR", 16, (0.19, 0.10, 0.02)),
]
PALETTES = {
    "ember": [
        (0.93, 0.47, 0.29, 1),
        (0.14, 0.12, 0.19, 1),
        (0.82, 0.57, 0.40, 1),
        (0.22, 0.08, 0.06, 1),
        (1, 0.77, 0.34, 1),
        (0.93, 0.91, 0.83, 1),
    ],
    "flux": [
        (0.16, 0.67, 0.83, 1),
        (0.09, 0.15, 0.24, 1),
        (0.78, 0.60, 0.49, 1),
        (0.78, 0.89, 0.92, 1),
        (0.55, 0.93, 1, 1),
        (0.94, 0.97, 1, 1),
    ],
    "terra": [
        (0.65, 0.48, 0.21, 1),
        (0.17, 0.23, 0.22, 1),
        (0.63, 0.43, 0.29, 1),
        (0.12, 0.13, 0.12, 1),
        (0.96, 0.80, 0.42, 1),
        (0.86, 0.87, 0.79, 1),
    ],
    "nyx": [
        (0.46, 0.29, 0.72, 1),
        (0.12, 0.10, 0.23, 1),
        (0.77, 0.59, 0.55, 1),
        (0.08, 0.06, 0.14, 1),
        (0.77, 0.65, 1, 1),
        (0.90, 0.87, 0.98, 1),
    ],
}


def quat(x=0, y=0, z=0):
    cx, sx = math.cos(x / 2), math.sin(x / 2)
    cy, sy = math.cos(y / 2), math.sin(y / 2)
    cz, sz = math.cos(z / 2), math.sin(z / 2)
    return (
        sx * cy * cz + cx * sy * sz,
        cx * sy * cz - sx * cy * sz,
        cx * cy * sz + sx * sy * cz,
        cx * cy * cz - sx * sy * sz,
    )


class Model:
    def __init__(self, char):
        self.char = char
        self.parts = {}
        self.width = 1.18 if char == "terra" else 0.93 if char == "nyx" else 1

    def rings(self, sections, bone, mat, n=12):
        # Rings: centre xyz and ellipse radii, yielding a closed sculpted surface.
        positions = []
        for x, y, z, rx, rz in sections:
            for j in range(n):
                a = j / n * math.tau
                positions.append((x + math.cos(a) * rx, y, z + math.sin(a) * rz))
        triangles = []
        for k in range(len(sections) - 1):
            for j in range(n):
                a = k * n + j
                b = k * n + (j + 1) % n
                c = (k + 1) * n + j
                d = (k + 1) * n + (j + 1) % n
                triangles.extend([(a, c, b), (b, c, d)])
        # Preserve crisp facets while skin joints keep parts connected.
        vertices = self.parts.setdefault(mat, [])
        for ids in triangles:
            a, b, c = [positions[q] for q in ids]
            u = [b[q] - a[q] for q in range(3)]
            v = [c[q] - a[q] for q in range(3)]
            normal = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            length = math.sqrt(sum(x * x for x in normal)) or 1
            normal = tuple(x / length for x in normal)
            for p in (a, b, c):
                vertices.append((p, normal, bone))

    def ellipsoid(self, x, y, z, rx, ry, rz, bone, mat, n=12):
        self.rings(
            [
                (x, y - ry, z, 0.001, 0.001),
                (x, y - ry * 0.72, z, rx * 0.72, rz * 0.72),
                (x, y, z, rx, rz),
                (x, y + ry * 0.72, z, rx * 0.72, rz * 0.72),
                (x, y + ry, z, 0.001, 0.001),
            ],
            bone,
            mat,
            n,
        )

    def build(self):
        w = self.width
        self.rings(
            [
                (0, 1.04, 0, 0.24 * w, 0.15),
                (0, 1.14, 0, 0.25 * w, 0.17),
                (0, 1.42, 0, 0.30 * w, 0.19),
                (0, 1.72, 0, 0.38 * w, 0.21),
                (0, 1.86, 0, 0.30 * w, 0.18),
                (0, 1.96, 0, 0.13, 0.12),
            ],
            3,
            0,
        )
        self.rings([(0, 0.90, 0, 0.24, 0.16), (0, 1.04, 0, 0.27, 0.18), (0, 1.17, 0, 0.25, 0.16)], 1, 1)
        self.rings([(0, 1.08, 0, 0.27, 0.19), (0, 1.16, 0, 0.29, 0.20), (0, 1.20, 0, 0.25, 0.17)], 1, 4)
        self.ellipsoid(0, 2.03, 0, 0.105, 0.15, 0.10, 4, 2)
        # Angular anime face and cheek silhouette.
        self.rings(
            [
                (0, 2.04, 0.055, 0.08, 0.07),
                (0, 2.09, 0.04, 0.15, 0.12),
                (0, 2.19, 0, 0.22, 0.18),
                (0, 2.34, -0.015, 0.24, 0.19),
                (0, 2.47, -0.025, 0.17, 0.13),
                (0, 2.50, -0.02, 0.02, 0.02),
            ],
            5,
            2,
            16,
        )
        self.ellipsoid(0, 2.225, 0.181, 0.035, 0.055, 0.048, 5, 2, 8)
        for side in (-1, 1):
            self.ellipsoid(side * 0.09, 2.30, 0.167, 0.061, 0.035, 0.014, 5, 5, 8)
            self.ellipsoid(side * 0.09, 2.30, 0.182, 0.023, 0.028, 0.007, 5, 3, 8)
            self.ellipsoid(side * 0.09, 2.35, 0.165, 0.068, 0.017, 0.014, 5, 3, 8)
            self.ellipsoid(side * 0.21, 2.25, -0.01, 0.047, 0.08, 0.045, 5, 2, 8)
        # Hair cap and asymmetric sculpted tufts.
        self.rings(
            [
                (0, 2.29, -0.07, 0.20, 0.17),
                (0, 2.42, -0.03, 0.265, 0.22),
                (0, 2.54, -0.05, 0.21, 0.18),
                (0, 2.60, -0.06, 0.04, 0.05),
            ],
            5,
            3,
        )
        for j in range(9):
            angle = j / 9 * math.tau
            x = math.cos(angle) * 0.19
            z = math.sin(angle) * 0.16 - 0.025
            height = 0.31 if self.char in ("ember", "flux") else 0.17
            self.rings(
                [
                    (x, 2.43, z, 0.085, 0.08),
                    (x * 1.2, 2.54, z * 1.2, 0.075, 0.065),
                    (
                        x * 1.5 + (0.08 if j % 2 else -0.02),
                        2.55 + height * (0.6 + 0.4 * math.sin(j * 2) ** 2),
                        z * 1.5 - 0.05,
                        0.002,
                        0.002,
                    ),
                ],
                5,
                3,
                6,
            )
        if self.char in ("flux", "nyx"):
            self.rings(
                [
                    (0, 2.43, -0.21, 0.10, 0.07),
                    (0.06, 2.2, -0.30, 0.13, 0.10),
                    (0.13, 1.88, -0.32, 0.09, 0.08),
                    (0.18, 1.60, -0.29, 0.01, 0.01),
                ],
                5,
                3,
            )
        # Arms, wrapped forearms, articulated hands and boots.
        for side, upper, fore, hand, thigh, shin, foot in [
            (-1, 6, 7, 8, 12, 13, 14),
            (1, 9, 10, 11, 15, 16, 17),
        ]:
            self.ellipsoid(side * 0.40, 1.86, 0, 0.18 * w, 0.20, 0.19, upper, 0)
            self.rings(
                [
                    (side * 0.43, 1.85, 0, 0.13 * w, 0.13),
                    (side * 0.48, 1.66, 0, 0.14 * w, 0.14),
                    (side * 0.53, 1.48, 0, 0.10, 0.10),
                ],
                upper,
                2,
            )
            self.rings(
                [
                    (side * 0.53, 1.50, 0, 0.11, 0.11),
                    (side * 0.55, 1.37, 0, 0.135, 0.14),
                    (side * 0.58, 1.13, 0.02, 0.085, 0.09),
                ],
                fore,
                1,
            )
            for y in (1.23, 1.30, 1.38):
                self.rings(
                    [(side * 0.56, y, 0, 0.13, 0.14), (side * 0.56, y + 0.035, 0, 0.135, 0.145)], fore, 4
                )
            self.ellipsoid(side * 0.58, 1.06, 0.045, 0.105, 0.13, 0.09, hand, 2)
            self.rings(
                [
                    (side * 0.18, 1.02, 0, 0.16, 0.16),
                    (side * 0.19, 0.78, -0.01, 0.18, 0.16),
                    (side * 0.19, 0.54, 0, 0.115, 0.11),
                ],
                thigh,
                1,
            )
            self.rings(
                [
                    (side * 0.19, 0.56, 0, 0.12, 0.12),
                    (side * 0.19, 0.32, 0, 0.15, 0.14),
                    (side * 0.19, 0.12, 0.02, 0.12, 0.14),
                ],
                shin,
                0,
            )
            self.ellipsoid(side * 0.19, 0.09, 0.13, 0.145, 0.09, 0.24, foot, 1)
            self.rings(
                [(side * 0.19, 0.18, 0.015, 0.14, 0.15), (side * 0.19, 0.23, 0.01, 0.15, 0.16)], shin, 4
            )
            # Split coat tails follow thighs; a real shaped mesh, not boxes.
            self.rings(
                [
                    (side * 0.22, 1.13, -0.05, 0.15, 0.18),
                    (side * 0.27, 0.93, -0.08, 0.20, 0.20),
                    (side * 0.31, 0.65, -0.10, 0.20, 0.18),
                    (side * 0.30, 0.58, -0.09, 0.10, 0.13),
                ],
                thigh,
                0,
                8,
            )
        # Chest emblem, layered collar and belt knot.
        self.ellipsoid(0, 1.65, 0.215, 0.085, 0.14, 0.025, 3, 4, 6)
        self.rings([(0, 1.91, 0, 0.18, 0.16), (0, 2.03, -0.02, 0.16, 0.15)], 4, 1)
        self.ellipsoid(0.10, 1.14, 0.22, 0.11, 0.08, 0.06, 1, 0)
        return self


class GLB:
    def __init__(self):
        self.data = bytearray()
        self.views = []
        self.accessors = []

    def accessor(self, values, kind, component=5126, limits=False):
        count = len(values)
        width = {"SCALAR": 1, "VEC3": 3, "VEC4": 4, "MAT4": 16}[kind]
        flat = [x for v in values for x in (v if isinstance(v, (tuple, list)) else [v])]
        while len(self.data) % 4:
            self.data.append(0)
        offset = len(self.data)
        fmt = "f" if component == 5126 else "H"
        self.data += struct.pack("<" + fmt * len(flat), *flat)
        self.views.append(dict(buffer=0, byteOffset=offset, byteLength=len(self.data) - offset))
        accessor = dict(bufferView=len(self.views) - 1, componentType=component, count=count, type=kind)
        if limits:
            accessor.update(
                min=[min(flat[i::width]) for i in range(width)],
                max=[max(flat[i::width]) for i in range(width)],
            )
        self.accessors.append(accessor)
        return len(self.accessors) - 1

    def write(self, model, path):
        nodes = []
        for name, parent, pos in BONES:
            parentpos = BONES[parent][2] if parent >= 0 else (0, 0, 0)
            nodes.append(dict(name=name, translation=[pos[i] - parentpos[i] for i in range(3)], children=[]))
        for i, (_, parent, _) in enumerate(BONES):
            if parent >= 0:
                nodes[parent]["children"].append(i)
        inverse = []
        for _, _, (x, y, z) in BONES:
            inverse.append([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, -x, -y, -z, 1])
        skin = dict(
            name="EclipseHumanoid",
            joints=list(range(len(BONES))),
            skeleton=0,
            inverseBindMatrices=self.accessor(inverse, "MAT4"),
        )
        primitives = []
        for material, vertices in model.parts.items():
            primitives.append(
                dict(
                    attributes=dict(
                        POSITION=self.accessor([v[0] for v in vertices], "VEC3", limits=True),
                        NORMAL=self.accessor([v[1] for v in vertices], "VEC3"),
                        JOINTS_0=self.accessor([(v[2], 0, 0, 0) for v in vertices], "VEC4", 5123),
                        WEIGHTS_0=self.accessor([(1.0, 0.0, 0.0, 0.0) for v in vertices], "VEC4"),
                    ),
                    material=material,
                )
            )
        nodes.append(dict(name=model.char, mesh=0, skin=0))
        clips = []
        for name, duration in [
            ("idle", 2),
            ("walk", 0.65),
            ("guard_high", 1),
            ("guard_low", 1),
            ("crouch", 1),
            ("jump", 0.7),
            ("dash_forward", 0.3),
            ("dash_back", 0.3),
            ("evade", 0.3),
            ("charge", 1.4),
            ("light", 0.35),
            ("heavy", 0.7),
            ("low", 0.55),
            ("overhead", 0.8),
            ("launcher", 0.75),
            ("throw", 0.7),
            ("air_heavy", 0.55),
            ("bolt", 0.65),
            ("beam", 1.6),
            ("signature", 1),
            ("ultimate", 1.5),
            ("hurt", 0.4),
            ("knockdown", 1),
            ("victory", 2),
            ("finisher", 5),
        ]:
            times = [duration * i / 32 for i in range(33)]
            timeacc = self.accessor(times, "SCALAR", limits=True)
            channels = []
            samplers = []
            for bone in range(1, len(BONES)):
                rotations = [pose(name, t / duration, bone, model.char) for t in times]
                out = self.accessor([quat(*angles) for angles in rotations], "VEC4")
                samplers.append(dict(input=timeacc, output=out, interpolation="LINEAR"))
                channels.append(dict(sampler=len(samplers) - 1, target=dict(node=bone, path="rotation")))
            clips.append(dict(name=name, samplers=samplers, channels=channels))
        materials = [
            dict(
                name=["fabric", "ink", "skin", "hair", "energy", "eyes"][i],
                pbrMetallicRoughness=dict(baseColorFactor=color, metallicFactor=0, roughnessFactor=0.8),
                doubleSided=True,
            )
            for i, color in enumerate(PALETTES[model.char])
        ]
        materials[4]["emissiveFactor"] = list(PALETTES[model.char][4][:3])
        doc = dict(
            asset=dict(version="2.0", generator="System One original character pipeline; CC0"),
            scene=0,
            scenes=[dict(nodes=[0, len(nodes) - 1])],
            nodes=nodes,
            meshes=[dict(primitives=primitives)],
            skins=[skin],
            animations=clips,
            materials=materials,
            buffers=[dict(byteLength=len(self.data))],
            bufferViews=self.views,
            accessors=self.accessors,
        )
        data = json.dumps(doc, separators=(",", ":")).encode()
        data += b" " * ((-len(data)) % 4)
        self.data += b"\0" * ((-len(self.data)) % 4)
        raw = (
            struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(data) + 8 + len(self.data))
            + struct.pack("<II", len(data), 0x4E4F534A)
            + data
            + struct.pack("<II", len(self.data), 0x004E4942)
            + self.data
        )
        path.write_bytes(raw)


def pose(name, p, bone, char):
    angles = [0.0, 0.0, 0.0]
    if bone in (6, 9):
        angles = [-0.45 if bone == 6 else -0.65, 0, -0.08 if bone == 6 else 0.08]
    if bone in (7, 10):
        angles = [-0.9, 0, 0]
    strike = math.sin(math.pi * p) ** 0.65
    if name == "idle":
        if bone == 3:
            angles[0] = math.sin(p * math.tau) * 0.025
        if bone in (12, 15):
            angles[0] = 0.04 * math.sin(p * math.tau)
    elif name == "walk":
        if bone in (12, 15):
            angles[0] = math.sin(p * math.tau) * (0.65 if bone == 12 else -0.65)
        if bone in (13, 16):
            angles[0] = max(0, math.sin(p * math.tau + (0 if bone == 13 else math.pi))) * 0.65
        if bone in (6, 9):
            angles[0] += 0.25 * math.sin(p * math.tau + (0 if bone == 6 else math.pi))
    elif name in ("guard_high", "guard_low", "crouch"):
        if bone in (6, 9):
            angles[0] = -1.15
        if bone in (7, 10):
            angles[0] = -1.4
        if name != "guard_high":
            if bone in (12, 15):
                angles[0] = -0.7
            if bone in (13, 16):
                angles[0] = 1.2
            if bone == 2:
                angles[0] = 0.4
    elif name in ("jump", "air_heavy"):
        if bone in (12, 15):
            angles[0] = -0.7 if bone == 12 else -0.35
        if bone in (13, 16):
            angles[0] = 0.9
        if name == "air_heavy" and bone == 12:
            angles[0] = -1.6 * strike
    elif name.startswith("dash") or name == "evade":
        if bone == 2:
            angles[0] = 0.45
        if bone == 12:
            angles[0] = -0.75
        if bone == 15:
            angles[0] = 0.75
        if bone in (6, 9):
            angles[0] = 0.4
    elif name in ("light", "heavy", "low", "overhead", "launcher", "throw", "signature"):
        kick = name in ("heavy", "low")
        if bone == 6:
            angles[0] = -0.45 - 1.15 * strike
        if bone == 7:
            angles[0] = -0.9 * (1 - strike)
        if bone == 3:
            angles[1] = -0.3 * strike
        if kick and bone == 12:
            angles[0] = -1.5 * strike
        if kick and bone == 13:
            angles[0] = 0.3 * (1 - strike)
        if name == "overhead" and bone in (6, 9):
            angles[0] = -2.6 * strike
        if name == "launcher" and bone == 6:
            angles[0] = -2.9 * strike
        if name == "signature" and char == "nyx" and bone in (6, 9):
            angles[0] = -1.6
        if name == "signature" and char == "ember" and bone in (6, 9):
            angles[0] = -1.2 - 0.4 * math.sin(p * math.pi * 6)
    elif name in ("charge", "bolt", "beam", "ultimate", "finisher"):
        if bone in (6, 9):
            angles[0] = -0.7 if name == "charge" else -1.4 * min(1, p * 4) - 0.2
            angles[2] = (-0.3 if bone == 6 else 0.3) if name == "charge" else 0
        if bone in (7, 10):
            angles[0] = -0.7 if name == "charge" else -0.8 * (1 - min(1, p * 3))
        if name in ("ultimate", "finisher") and bone in (6, 9):
            angles[0] = -2.8 if p < 0.3 else -1.6
        if name == "charge" and bone == 3:
            angles[0] = math.sin(p * math.tau) * 0.06
    elif name == "hurt":
        if bone == 2:
            angles[0] = -0.35 * strike
        if bone == 5:
            angles[0] = -0.25 * strike
    elif name == "knockdown":
        if bone == 1:
            angles[0] = -1.5
        if bone in (6, 9):
            angles[0] = 0.3
    elif name == "victory":
        if bone == 9:
            angles[0] = -2.9
        if bone == 10:
            angles[0] = -0.5
    return angles


if __name__ == "__main__":
    directory = ROOT / "frontend/public/assets/combat/fighters"
    directory.mkdir(parents=True, exist_ok=True)
    for character in PALETTES:
        path = directory / (character + ".glb")
        GLB().write(Model(character).build(), path)
        print(character, path.stat().st_size)
