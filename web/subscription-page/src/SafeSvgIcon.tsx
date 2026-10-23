import { useMemo, type ReactNode } from "react";

const SVG_NS = "http://www.w3.org/2000/svg";
const XLINK_NS = "http://www.w3.org/1999/xlink";
const SAFE_TAGS = new Set([
  "svg", "g", "path", "rect", "circle", "ellipse", "line", "polygon", "polyline",
  "defs", "lineargradient", "radialgradient", "stop", "clippath", "mask",
  "pattern", "symbol", "use", "title", "desc", "text", "tspan",
]);
const SAFE_ATTRS = new Set([
  "xmlns", "xmlns:xlink", "version", "viewbox", "preserveaspectratio", "width", "height",
  "x", "y", "x1", "x2", "y1", "y2", "cx", "cy", "r", "rx", "ry", "fx", "fy", "fr",
  "d", "points", "transform", "id", "class", "opacity", "fill", "stroke",
  "fill-opacity", "stroke-opacity", "fill-rule", "clip-rule", "stroke-width",
  "stroke-linecap", "stroke-linejoin", "stroke-miterlimit", "stroke-dasharray",
  "stroke-dashoffset", "vector-effect", "shape-rendering", "clip-path", "mask",
  "offset", "stop-color", "stop-opacity", "gradientunits", "gradienttransform",
  "spreadmethod", "patternunits", "patterncontentunits", "patterntransform",
  "font-size", "font-weight", "font-family", "text-anchor", "dominant-baseline",
  "href", "xlink:href", "aria-hidden", "aria-label", "role", "focusable",
]);
const SAFE_STYLE_PROPERTIES = new Set([
  "fill", "stroke", "opacity", "fill-opacity", "stroke-opacity", "fill-rule",
  "clip-rule", "stroke-width", "stroke-linecap", "stroke-linejoin",
  "stroke-miterlimit", "stroke-dasharray", "stroke-dashoffset", "stop-color",
  "stop-opacity", "font-size", "font-weight", "font-family", "text-anchor",
]);
const FRAGMENT_URL = /^url\(\s*["']?#[A-Za-z_][\w.:-]*["']?\s*\)$/i;
const SAFE_FRAGMENT = /^#[A-Za-z_][\w.:-]*$/;

/**
 * Strict, locally executed allowlist for operator-imported SVG. Unknown tags
 * and external references are rejected; unrecognized harmless attributes are
 * discarded. The output is used only as a passive <img>, never inline HTML.
 */
export function sanitizeSvg(svg: string): string | null {
  if (typeof svg !== "string" || svg.length === 0 || svg.length > 262144 ||
      /<!doctype|<!entity|<\?xml-stylesheet/i.test(svg)) return null;
  try {
    const doc = new DOMParser().parseFromString(svg, "image/svg+xml");
    const root = doc.documentElement;
    if (!root || root.localName.toLowerCase() !== "svg" ||
        root.namespaceURI !== SVG_NS || doc.querySelector("parsererror")) return null;
    const all = [root, ...Array.from(root.querySelectorAll("*"))];
    if (all.length > 2500) return null;
    for (const el of all) {
      if (el.namespaceURI !== SVG_NS || !SAFE_TAGS.has(el.localName.toLowerCase())) return null;
      for (const attr of Array.from(el.attributes)) {
        const name = attr.name.toLowerCase();
        const value = attr.value.trim();
        if (name.startsWith("on") || attr.namespaceURI && attr.namespaceURI !== XLINK_NS &&
            attr.namespaceURI !== "http://www.w3.org/2000/xmlns/") return null;
        if (name === "xmlns" || name === "xmlns:xlink") {
          if (value !== (name === "xmlns" ? SVG_NS : XLINK_NS)) return null;
          continue;
        }
        if (name === "href" || name === "xlink:href") {
          if (!SAFE_FRAGMENT.test(value)) return null;
          continue;
        }
        if (name === "style") {
          const declarations = value.split(";").filter(Boolean);
          if (declarations.length > 32) return null;
          for (const declaration of declarations) {
            const at = declaration.indexOf(":");
            if (at <= 0) return null;
            const prop = declaration.slice(0, at).trim().toLowerCase();
            const v = declaration.slice(at + 1).trim();
            if (!SAFE_STYLE_PROPERTIES.has(prop) || !v || /[;{}<>\\]/.test(v) ||
                (/url\(/i.test(v) && !FRAGMENT_URL.test(v)) ||
                /@import|expression|javascript:|data:|https?:|file:|blob:/i.test(v)) return null;
          }
          continue;
        }
        if (!SAFE_ATTRS.has(name)) {
          el.removeAttributeNode(attr);
          continue;
        }
        if (/url\(/i.test(value)) {
          if (!["fill", "stroke", "clip-path", "mask"].includes(name) ||
              !FRAGMENT_URL.test(value)) return null;
        } else if (/@import|expression|javascript:|data:|https?:|file:|blob:|[<>]/i.test(value)) {
          return null;
        }
      }
    }
    // Removes XML declarations, comments and all unknown attributes.
    root.setAttribute("xmlns", SVG_NS);
    return new XMLSerializer().serializeToString(root);
  } catch {
    return null;
  }
}

export function parseLocalSvgLibrary(raw: string): Record<string, string> {
  if (new TextEncoder().encode(raw).length > 4194304) throw new Error("SVG library too large");
  const value: unknown = JSON.parse(raw);
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid SVG library");
  const root = value as Record<string, unknown>;
  const lib: unknown = Object.hasOwn(root, "svgLibrary") ? root.svgLibrary : root;
  if (!lib || typeof lib !== "object" || Array.isArray(lib)) throw new Error("Invalid svgLibrary");
  const entries = Object.entries(lib as Record<string, unknown>);
  if (entries.length < 1 || entries.length > 80) throw new Error("Invalid SVG library size");
  const output: Record<string, string> = Object.create(null);
  for (const [key, svg] of entries) {
    if (!/^[\w-]{1,64}$/.test(key) || typeof svg !== "string") throw new Error("Invalid SVG entry");
    // Quarantine unsafe entries by not putting them into the usable library.
    if (sanitizeSvg(svg)) output[key] = svg;
  }
  return output;
}

export function SafeSvgIcon({ iconKey, library, fallback, testId, className }: {
  iconKey?: string;
  library?: Record<string, string>;
  fallback: ReactNode;
  testId?: string;
  className?: string;
}) {
  const xml = iconKey ? library?.[iconKey] : undefined;
  const uri = useMemo(() => {
    if (!xml) return null;
    const clean = sanitizeSvg(xml);
    return clean ? "data:image/svg+xml;charset=utf-8," + encodeURIComponent(clean) : null;
  }, [xml]);
  if (!uri) return <>{fallback}</>;
  return <img data-testid={testId ?? "safe-svg-icon"} className={className}
    src={uri} alt="" aria-hidden="true" draggable={false} decoding="async"/>;
}
