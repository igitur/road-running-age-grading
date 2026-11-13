#!/usr/bin/env node
/**
 * js_oracle.js — ground-truth harness for the MLDR road age-grading calculator.
 *
 * Extracts the <script> block from the published calculator page
 * (mldrroad25.html) and runs THAT code inside a stubbed DOM, so we can compare
 * our own port against the real thing rather than against our reading of it.
 *
 * Input (stdin): JSON array of requests:
 *   {"sex":"M"|"F", "age":<number>, "version":0..3,
 *    "event":"10kmRoad" | null, "distance_km":<number> | null,
 *    "time":"mm:ss"|"h:mm:ss"|"<seconds>"}
 * Output (stdout): JSON array of results:
 *   {"afac","ostd","astd","ageresult","aplp"}  (population as the UI shows them)
 *
 * Usage: node tools/js_oracle.js page.html < requests.json > out.json
 */
const fs = require("fs");
const vm = require("vm");

const pagePath = process.argv[2] || "page.html";
const html = fs.readFileSync(pagePath, "utf8");

// ---- pull the calculator script (the one that defines MLDR_25_M_facs) -------
const blocks = [...html.matchAll(/<script[^>]*>([\s\S]*?)<\/script>/gi)].map(
  (m) => m[1]
);
const calc = blocks.find((b) => b.includes("MLDR_25_M_facs"));
if (!calc) throw new Error("calculator script block not found in page");

// static <option> list of the event dropdown, as the real page ships it
const roadBlock = html.match(/<select name="road"[\s\S]*?<\/select>/i)[0];
const staticOptions = [...roadBlock.matchAll(/<option value="([^"]*)"/gi)].map(
  (m) => m[1]
);

// ---- minimal DOM stub ------------------------------------------------------
class Option {
  constructor(text, value) {
    this.text = text;
    this.value = value;
  }
}
function makeSelect() {
  const sel = { options: [], selectedIndex: 0, value: "" };
  return new Proxy(sel, {
    get(t, k) {
      if (k === "length") return t.options.length;
      if (typeof k === "string" && /^\d+$/.test(k)) return t.options[+k];
      if (k in t) return t[k];
      return t.options[t.selectedIndex] ? t.options[t.selectedIndex][k] : undefined;
    },
    set(t, k, v) {
      if (typeof k === "string" && /^\d+$/.test(k)) {
        t.options[+k] = v;
        return true;
      }
      t[k] = v;
      return true;
    },
  });
}
const field = (v = "") => ({ value: v });
const roadSelect = makeSelect();
staticOptions.forEach((v, i) => {
  roadSelect.options[i] = new Option(v, v);
});
roadSelect.selectedIndex = 0;
const form = {
  wmavsn: { selectedIndex: 0, options: [{ value: "2025" }] },
  road: roadSelect,
  mileage: field(""),
  milkm: field("1.0"),
  ageBox: field(""),
  result: field(""),
  ageresult: field(""),
  aplp: field(""),
  afac: field(""),
  ostd: field(""),
  astd: field(""),
  debug: field(""),
};
const ctx = {
  form,
  Option,
  console,
  document: { dataform: form },
  Math,
  Array,
  parseFloat,
  parseInt,
  isNaN,
};
vm.createContext(ctx);
vm.runInContext(calc, ctx);

// ---- drive it --------------------------------------------------------------
function grade(req) {
  form.wmavsn.selectedIndex = req.version ?? 0;
  const ev = req.event ?? "";
  // setFactors() calls setEventOptions() which rebuilds options from `factors`
  form.road.selectedIndex = 0;
  form.road.value = ev;
  ctx.setFactors(req.sex);
  try {
    if (req.event) {
      const idx = form.road.options.findIndex((o) => o.value === req.event);
      if (idx >= 0) form.road.selectedIndex = idx;
      ctx.setEvent();
    } else if (req.distance_km) {
      form.road.selectedIndex = 0;
      form.mileage.value = String(req.distance_km);
      form.milkm.value = "1.0"; // km
      ctx.setMileage();
    }
    form.ageBox.value = String(req.age);
    ctx.setAge();
    form.result.value = req.time;
    ctx.calc_fwd();
  } catch (e) {
    return { error: String(e) };
  }
  return {
    afac: form.afac.value,
    ostd: form.ostd.value,
    astd: form.astd.value,
    ageresult: form.ageresult.value,
    aplp: form.aplp.value,
  };
}

const reqs = JSON.parse(fs.readFileSync(0, "utf8"));
process.stdout.write(JSON.stringify(reqs.map(grade), null, 1));
