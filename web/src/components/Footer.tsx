import { FOOTER_TEXT } from "../config";
import "./Footer.css";

export function Footer() {
  return (
    <footer className="footer">
      <p>{FOOTER_TEXT}</p>
    </footer>
  );
}
