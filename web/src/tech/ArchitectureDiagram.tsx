import { useMediaQuery } from "../state/useMediaQuery";
import { Panel } from "./Panel";

type Group = "loop" | "browser";

interface Node {
  id: string;
  name: string;
  sub: string;
  group: Group;
}

/** The eight stages, in flow order. */
const NODES: readonly Node[] = [
  { id: "teacher", name: "Teacher", sub: "an open model, run by us", group: "loop" },
  { id: "lessons", name: "Lessons", sub: "invented chats, labelled", group: "loop" },
  { id: "student", name: "Student", sub: "a small encoder, fine-tuned", group: "loop" },
  { id: "calibration", name: "Calibration", sub: "temperature, none, cut-offs", group: "loop" },
  { id: "exam", name: "Sealed exam", sub: "people never trained on", group: "loop" },
  { id: "scoreboard", name: "Scoreboard", sub: "every run published", group: "loop" },
  { id: "worker", name: "Browser worker", sub: "WebGPU or WASM, on your device", group: "browser" },
  { id: "bundles", name: "Bundles", sub: "file · suggest · leave loose", group: "browser" },
];

const LOOP_LABEL = "Learning loop · a laptop at toy scale today, a DGX Spark next";
const LOOP_LABEL_NARROW = "Learning loop · toy scale today";
const BROWSER_LABEL = "In the browser · running on this page";

interface Box {
  x: number;
  y: number;
}

interface Layout {
  width: number;
  height: number;
  nodeW: number;
  nodeH: number;
  boxes: Box[];
  /** SVG path data for each edge, from node i to node i + 1. */
  edges: string[];
  loopRect: { x: number; y: number; w: number; h: number };
  browserRect: { x: number; y: number; w: number; h: number };
  labelX: number;
  loopLabelY: number;
  browserLabelY: number;
}

/** Three nodes per row; the flow turns down and back at the end of each row. */
function wideLayout(): Layout {
  const nodeW = 200;
  const nodeH = 60;
  const cols = [20, 260, 500];
  const rows = [32, 140, 252];
  const boxes: Box[] = NODES.map((_, i) => ({
    x: cols[i % 3] ?? 0,
    y: rows[Math.floor(i / 3)] ?? 0,
  }));
  const edges: string[] = [];
  for (let i = 0; i < boxes.length - 1; i += 1) {
    const a = boxes[i] as Box;
    const b = boxes[i + 1] as Box;
    if (a.y === b.y) {
      edges.push(`M${a.x + nodeW} ${a.y + nodeH / 2} H${b.x}`);
    } else {
      const midY = a.y + nodeH + (b.y - a.y - nodeH) / 2;
      edges.push(`M${a.x + nodeW / 2} ${a.y + nodeH} V${midY} H${b.x + nodeW / 2} V${b.y}`);
    }
  }
  return {
    width: 720,
    height: 340,
    nodeW,
    nodeH,
    boxes,
    edges,
    loopRect: { x: 8, y: 4, w: 704, h: 208 },
    browserRect: { x: 8, y: 224, w: 704, h: 108 },
    labelX: 700,
    loopLabelY: 22,
    browserLabelY: 242,
  };
}

/** One node per row, for phones. */
function narrowLayout(): Layout {
  const nodeW = 300;
  const nodeH = 60;
  const pitch = 84;
  const x = 30;
  const boxes: Box[] = NODES.map((node, i) => ({
    x,
    y: node.group === "loop" ? 32 + i * pitch : 560 + (i - 6) * pitch,
  }));
  const edges: string[] = [];
  for (let i = 0; i < boxes.length - 1; i += 1) {
    const a = boxes[i] as Box;
    const b = boxes[i + 1] as Box;
    edges.push(`M${a.x + nodeW / 2} ${a.y + nodeH} V${b.y}`);
  }
  return {
    width: 360,
    height: 724,
    nodeW,
    nodeH,
    boxes,
    edges,
    loopRect: { x: 8, y: 4, w: 344, h: 520 },
    browserRect: { x: 8, y: 532, w: 344, h: 184 },
    labelX: 340,
    loopLabelY: 22,
    browserLabelY: 550,
  };
}

const DESCRIPTION =
  "Eight stages in order. A teacher model writes lessons: invented chats, each labelled. " +
  "A student, a small encoder, learns from them. Calibration sets the temperature, the none " +
  "score and the two cut-offs. The student sits a sealed exam on people it never trained on. " +
  "The result is published on the scoreboard. The model then runs in a browser worker on the " +
  "visitor's device, which sorts their chats into bundles: file, suggest or leave loose.";

/** Our own drawing of the loop, in the site's tokens so it reads in both themes. */
export function ArchitectureDiagram() {
  const wide = useMediaQuery("(min-width: 48rem)");
  const layout = wide ? wideLayout() : narrowLayout();
  const { nodeW, nodeH } = layout;
  return (
    <Panel id="tech-arch" title="Architecture" wide defaultOpen={false}>
      <svg
        className="arch"
        viewBox={`0 0 ${layout.width} ${layout.height}`}
        role="img"
        aria-labelledby="arch-title arch-desc"
      >
        <title id="arch-title">How the sorter is built and where it runs</title>
        <desc id="arch-desc">{DESCRIPTION}</desc>
        <defs>
          <marker
            id="arch-arrow"
            viewBox="0 0 10 10"
            refX="9"
            refY="5"
            markerWidth="7"
            markerHeight="7"
            orient="auto-start-reverse"
          >
            <path d="M0 0 L10 5 L0 10 z" className="arch__arrow" />
          </marker>
        </defs>

        <rect
          className="arch__group"
          x={layout.loopRect.x}
          y={layout.loopRect.y}
          width={layout.loopRect.w}
          height={layout.loopRect.h}
          rx="14"
        />
        <text
          className="arch__group-label"
          x={layout.labelX}
          y={layout.loopLabelY}
          textAnchor="end"
        >
          {wide ? LOOP_LABEL : LOOP_LABEL_NARROW}
        </text>
        <rect
          className="arch__group arch__group--browser"
          x={layout.browserRect.x}
          y={layout.browserRect.y}
          width={layout.browserRect.w}
          height={layout.browserRect.h}
          rx="14"
        />
        <text
          className="arch__group-label"
          x={layout.labelX}
          y={layout.browserLabelY}
          textAnchor="end"
        >
          {BROWSER_LABEL}
        </text>

        {layout.edges.map((d, i) => (
          <path
            key={`${NODES[i]?.id}-${NODES[i + 1]?.id}`}
            className="arch__edge"
            d={d}
            markerEnd="url(#arch-arrow)"
          />
        ))}

        {NODES.map((node, i) => {
          const box = layout.boxes[i] as Box;
          return (
            <g
              key={node.id}
              className={node.group === "browser" ? "arch__node arch__node--browser" : "arch__node"}
            >
              <rect x={box.x} y={box.y} width={nodeW} height={nodeH} rx="10" />
              <text className="arch__step" x={box.x + nodeW - 12} y={box.y + 20} textAnchor="end">
                {i + 1}
              </text>
              <text className="arch__name" x={box.x + 14} y={box.y + 26}>
                {node.name}
              </text>
              <text className="arch__sub" x={box.x + 14} y={box.y + 45}>
                {node.sub}
              </text>
            </g>
          );
        })}
      </svg>
      <p className="tech__muted">
        The top half runs offline and writes the model and the scoreboard; the bottom half is this
        page. The site ships the base encoder until a student beats it on the sealed exam.
      </p>
    </Panel>
  );
}
