# Word Antakshari — Ads Compliance Checklist

Everything needed to get the site ready for Adsterra, then Google AdSense later.

---

## 1. Privacy Policy page (`/privacy` & modal)
Required by both Adsterra and AdSense. Must disclose:
- [x] That the site uses third-party ad networks (cookies/tracking used to show relevant ads)
- [x] What data is collected (gameplay data, IP/session info handled via Redis, etc.)
- [x] A contact email for privacy questions (`support.wordantakshari@gmail.com`)

*Implemented in [`lobby.ts`](file:///d:/WordAntakshari/Word-Antakshari/frontend/src/ui/lobby.ts) via `showPrivacyPolicyPopup()` accessible from the Options dropdown menu & footer links.*

---

## 2. About page (`/about` & modal)
- [x] Describes platform mission, technology architecture, and vision
- [x] Specifies founders & team (Krishna Dahipalle & Rathod Arun)
- [x] Makes the site look like a real, maintained project rather than a bare, anonymous page

*Implemented in [`lobby.ts`](file:///d:/WordAntakshari/Word-Antakshari/frontend/src/ui/lobby.ts) via dedicated `showAboutPopup()`.*

---

## 3. Contact page or section
- [x] A real email address players or ad-network reviewers can reach you at (`support.wordantakshari@gmail.com`)

*Implemented in [`lobby.ts`](file:///d:/WordAntakshari/Word-Antakshari/frontend/src/ui/lobby.ts) via `showContactPopup()`.*

---

## 4. Cookie consent banner
- [x] A simple banner: "This site uses cookies for ads and functionality" with an OK/dismiss button

*Implemented in [`lobby.ts`](file:///d:/WordAntakshari/Word-Antakshari/frontend/src/ui/lobby.ts) via `renderCookieConsent()` with persistent `localStorage` consent tracking.*

