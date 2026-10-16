import manifest from "../sorter/model-manifest.json";
import { Panel } from "./Panel";

/** What never leaves the browser, stated plainly. */
export function Privacy() {
  const local = manifest.source === "local";
  return (
    <Panel id="tech-privacy" title="Privacy" defaultOpen={false}>
      <p>
        There is no server behind this page. Everything you see is computed on your device, in a Web
        Worker. Your answers, chats and the sort are forgotten when you close the tab.
      </p>
      <ul className="tech__list">
        <li>
          Your quiz answers, anything you type, every chat and the whole sort stay in this browser
          tab. No request ever carries them.
        </li>
        <li>No cookies, no analytics, no fingerprinting, no localStorage or sessionStorage.</li>
        <li>
          The model files are kept in this browser's cache storage (the same place a browser keeps
          images), so a return visit skips the download. They are identical for every visitor and
          hold nothing about you; clearing this site's data removes them.
        </li>
        <li>
          {local
            ? "The model files come from this site's own /models/ folder; nothing is fetched from a third party."
            : "The only third-party request is the model download from huggingface.co. Its files are public and identical for every visitor, so the request says nothing about you."}
        </li>
        <li>
          The ONNX runtime and the fonts are served from this site, not from a content delivery
          network.
        </li>
        <li>
          The model never learns from what visitors do here: it is trained only on invented chats
          written by an open-licensed teacher model.
        </li>
      </ul>
    </Panel>
  );
}
