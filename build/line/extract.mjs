// Export a build plan's glyphs as stroke centerlines, using the pinned Iosevka as a library.
// node build/line/extract.mjs IOSEVKA_DIR PLANS.toml PLAN WEIGHT SLOPE_ANGLE OUT.json
// Run by `bash build/build.sh line`; write_svg.py turns the output into an SVG font.
import fs from "node:fs";
import path from "node:path";

const [iosevka, plansPath, planName, weightArg, angleArg, outPath] = process.argv.slice(2);
const imp = p => import(path.join(iosevka, p));

import { createRequire } from "node:module";
const require = createRequire(path.join(iosevka, "package.json"));
const Toml = require("@iarna/toml");
const { getParametersT } = await imp("packages/font/src/param/index.mjs");
const { buildGlyphs } = await imp("packages/font-glyphs/lib/index.mjs");
const Geom = await imp("packages/geometry/src/index.mjs");
const { SpiroExpander } = await imp("packages/geometry/src/spiro-expand.mjs");
const { spiroToBezArcsWithSimplification } = await imp(
	"packages/geometry/src/spiro-to-outline.mjs",
);
const { Transform } = await imp("packages/geometry/src/transform.mjs");
const TypoGeom = require("typo-geom");

await Geom.Init();
const plans = Toml.parse(fs.readFileSync(plansPath, "utf8")).buildPlans;
const bp = plans[planName];
const variantComposites = {};
for (const [k, v] of Object.entries(plans)) if (v.variants) variantComposites[k] = v.variants;
const ligComposites = {};
for (const [k, v] of Object.entries(plans)) if (v.ligations) ligComposites[`buildPlans.${k}`] = v.ligations;
const version = JSON.parse(fs.readFileSync(path.join(iosevka, "package.json"))).version;
const angle = Number(angleArg);
const argv = {
	name: planName,
	variants: bp.variants,
	featureControl: { noCvSs: true, noLigation: false, exportGlyphNames: false },
	ligations: bp.ligations,
	shape: {
		serifs: "sans",
		spacing: bp.spacing,
		weight: Number(weightArg),
		width: 500,
		slope: angle ? "italic" : "upright",
		slopeAngle: angle,
	},
	menu: { family: bp.family, version, width: 5, slope: angle ? "italic" : "normal", weight: 400 },
	css: { weight: 400, stretch: "normal", style: angle ? "italic" : "normal" },
	metricOverride: bp.metricOverride,
	variantCompositesFromBuildPlan: variantComposites,
	ligtionCompositesFromBuildPlan: ligComposites,
	paramsDir: path.join(iosevka, "params"),
};
const para = (await getParametersT(argv))(argv);
const { glyphStore } = buildGlyphs(para);
const CLIP = TypoGeom.Boolean.ClipType;

const compose = (inner, outer) => Transform.Combine(inner, outer); // inner first
const bezList = (arcs, tf) =>
	arcs.map(c =>
		c.map(a => {
			const p = q => [tf.applyX(q.x, q.y), tf.applyY(q.x, q.y)];
			return [p(a.a), p(a.b), p(a.c), p(a.d)];
		}),
	);

// A tree whose leaves are strokes (centerline + outline region) or fills (outline only).
function walk(g, tf) {
	if (g instanceof Geom.DiSpiroGeometry) {
		const ex = new SpiroExpander(g.m_gizmo, g.m_contrast, g.m_closed, g.m_biKnots);
		ex.initializeNormals();
		for (let r = 0; r < 8; r++) if (ex.iterateNormals() < 1e-8) break;
		// The centerline: midpoints of each knot's left and right offsets, before the slant.
		const { lhsUntransformed: lhs, rhsUntransformed: rhs } = ex.expand();
		const middles = lhs.map((l, j) => {
			const m = l.clone();
			m.x = (l.x + rhs[j].x) / 2;
			m.y = (l.y + rhs[j].y) / 2;
			return m;
		});
		if (!g.m_closed) middles[0].type = middles[middles.length - 1].type = "corner";
		const center = spiroToBezArcsWithSimplification(middles, g.m_closed, g.m_gizmo);
		// The conversion closes every contour with a line back to the start; an open
		// stroke ends before it.
		if (!g.m_closed) for (const c of center) if (c.length > 1) c.pop();
		return {
			kind: "stroke",
			closed: g.m_closed,
			center: bezList(center, tf),
			region: bezList(g.toBezArcs(), tf),
		};
	}
	if (
		g instanceof Geom.SpiroGeometry ||
		g instanceof Geom.ContourSetGeometry ||
		g instanceof Geom.StrokeGeometry ||
		g instanceof Geom.SpiroPenGeometry
	) {
		return { kind: "fill", region: bezList(g.toBezArcs(), tf) };
	}
	if (g instanceof Geom.CombineGeometry)
		return { kind: "union", children: g.m_parts.map(p => walk(p, tf)) };
	if (g instanceof Geom.BooleanGeometry) {
		const op = { [CLIP.Union]: "union", [CLIP.Intersection]: "intersection", [CLIP.Difference]: "difference" }[g.m_operator];
		if (!op) throw new Error(`boolean op ${g.m_operator}`);
		return { kind: op, children: g.m_operands.map(p => walk(p, tf)) };
	}
	if (g instanceof Geom.TransformedGeometry) return walk(g.m_geom, compose(g.m_transform, tf));
	if (g instanceof Geom.ReferenceGeometry)
		return walk(g.m_glyph.geometry, compose(Transform.Translate(g.m_x, g.m_y), tf));
	if (
		g instanceof Geom.TaggedGeometry ||
		g instanceof Geom.RadicalGeometry ||
		g instanceof Geom.RemoveHolesGeometry
	)
		return walk(g.m_geom, tf);
	throw new Error(`unknown geometry ${g.constructor.name}`);
}

const wanted = new Set();
for (let u = 0x20; u <= 0x7e; u++) wanted.add(u);
for (let u = 0xa0; u <= 0xff; u++) wanted.add(u);
// EMS Readability's other characters.
for (const u of [0x102, 0x103, 0x106, 0x107, 0x10c, 0x10d, 0x110, 0x111, 0x114, 0x115, 0x11e,
	0x11f, 0x12c, 0x12d, 0x130, 0x131, 0x14e, 0x14f, 0x15e, 0x15f, 0x160, 0x161, 0x16c, 0x16d,
	0x178, 0x17d, 0x17e, 0x2d8, 0x2013, 0x2014, 0x2018, 0x2019, 0x201c, 0x201d, 0x2039, 0x203a,
	0x20ac])
	wanted.add(u);
const out = { metrics: { cap: para.cap, xheight: para.xHeight, descender: para.descender, stroke: para.stroke, contrast: para.contrast }, glyphs: {} };
for (const [gn, glyph] of glyphStore.namedEntries()) {
	const us = [...(glyphStore.queryUnicodeOfName(gn) || [])].filter(u => wanted.has(u));
	if (!us.length) continue;
	out.glyphs[gn] = { unicodes: us, advance: glyph.advanceWidth, tree: walk(glyph.geometry, Transform.Id()) };
}
fs.writeFileSync(outPath, JSON.stringify(out));
console.log(`wrote ${Object.keys(out.glyphs).length} glyphs; stroke ${para.stroke}`);
