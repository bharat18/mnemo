/**
 * export_chat.js — Claude.ai Chat Exporter
 *
 * TWO WAYS TO USE:
 *
 * Option A — Browser Console (easiest):
 *   1. Open your Claude.ai chat
 *   2. Press F12 → Console tab
 *   3. Paste this entire file and press Enter
 *   4. A .md file downloads automatically
 *
 * Option B — Bookmarklet (one-click):
 *   1. Copy the minified line at the bottom of this file
 *   2. Create a new browser bookmark
 *   3. Paste it as the URL
 *   4. Click the bookmark on any Claude.ai chat page
 */

(function exportClaudeChat() {

  // ── Selector strategy: try multiple DOM patterns Claude.ai uses ────────────
  const SELECTORS = {
    human: [
      '[data-testid="human-turn"]',
      '.human-turn',
      '[class*="human"]',
    ],
    claude: [
      '[data-testid="ai-turn"]',
      '.ai-turn',
      '[class*="assistant"]',
      '[class*="Claude"]',
    ],
    // Generic fallback — grab all message containers in order
    generic: [
      '[class*="message"]',
      '[class*="conversation-turn"]',
      '[class*="turn"]',
    ],
  };

  /**
   * Try a list of selectors, return first that finds elements.
   */
  function queryFirst(selectors) {
    for (const sel of selectors) {
      try {
        const els = document.querySelectorAll(sel);
        if (els.length > 0) return Array.from(els);
      } catch (_) {}
    }
    return [];
  }

  /**
   * Extract clean text from an element, preserving code blocks.
   */
  function extractText(el) {
    // Preserve <code> blocks with backticks
    const clone = el.cloneNode(true);

    // Replace <pre><code> with fenced code blocks
    clone.querySelectorAll("pre code, pre").forEach((code) => {
      const lang = code.className?.match(/language-(\w+)/)?.[1] ?? "";
      const text = code.innerText ?? code.textContent ?? "";
      const fence = document.createTextNode(`\n\`\`\`${lang}\n${text}\n\`\`\`\n`);
      code.closest("pre")?.replaceWith(fence);
    });

    // Replace inline <code> with backticks
    clone.querySelectorAll("code").forEach((c) => {
      c.replaceWith(document.createTextNode("`" + c.innerText + "`"));
    });

    return (clone.innerText ?? clone.textContent ?? "").trim();
  }

  // ── Attempt structured extraction ─────────────────────────────────────────
  let lines = [];
  const humanEls = queryFirst(SELECTORS.human);
  const claudeEls = queryFirst(SELECTORS.claude);

  if (humanEls.length > 0 || claudeEls.length > 0) {
    // Structured extraction — we know which role each element is
    const allEls = Array.from(document.querySelectorAll(
      SELECTORS.human.concat(SELECTORS.claude).join(",")
    )).sort((a, b) => {
      // Sort by DOM order
      const pos = a.compareDocumentPosition(b);
      return pos & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
    });

    allEls.forEach((el) => {
      const isHuman =
        SELECTORS.human.some((s) => { try { return el.matches(s); } catch(_){return false;} });
      const role = isHuman ? "**Human**" : "**Claude**";
      const text = extractText(el);
      if (text) {
        lines.push(`${role}:\n${text}\n\n---\n`);
      }
    });

  } else {
    // Fallback: generic container extraction (role unknown)
    const genericEls = queryFirst(SELECTORS.generic);
    if (genericEls.length === 0) {
      alert(
        "❌ Could not find chat messages.\n\n" +
        "Make sure you are on a Claude.ai chat page with messages loaded.\n" +
        "If the issue persists, Claude.ai may have updated their HTML structure."
      );
      return;
    }
    let roleToggle = true; // alternate Human/Claude
    genericEls.forEach((el) => {
      const text = extractText(el);
      if (!text) return;
      const role = roleToggle ? "**Human**" : "**Claude**";
      roleToggle = !roleToggle;
      lines.push(`${role}:\n${text}\n\n---\n`);
    });
  }

  if (lines.length === 0) {
    alert("❌ No messages found. Try scrolling to load the full chat first.");
    return;
  }

  // ── Build markdown file ───────────────────────────────────────────────────
  const pageTitle = document.title.replace(/\s*[-|].*$/, "").trim() || "claude_chat";
  const timestamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const filename  = `${pageTitle}_${timestamp}.md`.replace(/[^\w\-_.]/g, "_");

  const header = [
    `# ${pageTitle}`,
    `Exported: ${new Date().toLocaleString()}`,
    `URL: ${location.href}`,
    `Messages: ${lines.length}`,
    "",
    "---",
    "",
  ].join("\n");

  const content = header + lines.join("\n");

  // ── Trigger download ──────────────────────────────────────────────────────
  const blob = new Blob([content], { type: "text/markdown;charset=utf-8" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);

  console.log(`✅ Mnemo Export: ${lines.length} messages → ${filename}`);
  alert(`✅ Exported ${lines.length} messages!\nFile: ${filename}\n\nNow run:\npython indexer.py "${filename}" --provider openai`);

})();


/* ============================================================================
   BOOKMARKLET VERSION — copy everything below this line into a bookmark URL
   ============================================================================

javascript:(function(){const S={human:['[data-testid="human-turn"]','.human-turn','[class*="human"]'],claude:['[data-testid="ai-turn"]','.ai-turn','[class*="assistant"]','[class*="Claude"]'],generic:['[class*="message"]','[class*="conversation-turn"]','[class*="turn"]']};function q(s){for(const x of s){try{const e=document.querySelectorAll(x);if(e.length>0)return Array.from(e);}catch(_){}}return[];}function t(el){const c=el.cloneNode(true);c.querySelectorAll('pre code,pre').forEach(e=>{const l=e.className?.match(/language-(\w+)/)?.[1]??'';const txt=e.innerText??'';const f=document.createTextNode('\n```'+l+'\n'+txt+'\n```\n');e.closest('pre')?.replaceWith(f);});c.querySelectorAll('code').forEach(e=>{e.replaceWith(document.createTextNode('`'+e.innerText+'`'));});return(c.innerText??c.textContent??'').trim();}let lines=[];const hEls=q(S.human),cEls=q(S.claude);if(hEls.length>0||cEls.length>0){const all=Array.from(document.querySelectorAll(S.human.concat(S.claude).join(','))).sort((a,b)=>a.compareDocumentPosition(b)&Node.DOCUMENT_POSITION_FOLLOWING?-1:1);all.forEach(el=>{const isH=S.human.some(s=>{try{return el.matches(s);}catch(_){return false;}});const r=isH?'**Human**':'**Claude**';const tx=t(el);if(tx)lines.push(r+':\n'+tx+'\n\n---\n');});}else{const g=q(S.generic);if(!g.length){alert('Could not find messages. Make sure you are on a Claude.ai chat page.');return;}let tog=true;g.forEach(el=>{const tx=t(el);if(!tx)return;lines.push((tog?'**Human**':'**Claude**')+':\n'+tx+'\n\n---\n');tog=!tog;});}if(!lines.length){alert('No messages found.');return;}const title=document.title.replace(/\s*[-|].*$/,'').trim()||'claude_chat';const ts=new Date().toISOString().replace(/[:.]/g,'-').slice(0,19);const fn=(title+'_'+ts+'.md').replace(/[^\w\-_.]/g,'_');const hdr='# '+title+'\nExported: '+new Date().toLocaleString()+'\nMessages: '+lines.length+'\n\n---\n\n';const blob=new Blob([hdr+lines.join('\n')],{type:'text/markdown'});const url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=fn;document.body.appendChild(a);a.click();document.body.removeChild(a);URL.revokeObjectURL(url);alert('Exported '+lines.length+' messages!\nFile: '+fn);})();

*/
