/** No exception, assertion values, stdout, DOM or attachment is serialized. */
export default class SafeReporter {
  /** @param {import("@playwright/test/reporter").TestCase} test @param {import("@playwright/test/reporter").TestResult} result */
  onTestEnd(test, result) { console.log(test.titlePath().join(" > ") + ": " + result.status + " duration-ms=" + result.duration + " " + test.annotations.filter(a=>["gate","check"].includes(a.type) && (a.description ?? "").split("|").every(v=>["assertion","roundtrip","three-calls","post-origin","redirect","sink-control","csrf-cors","csrf-form","port","version","action","exit","other","Browser harness failed.","harness-closing-browser","harness-browser-closed","harness-stopping-child","harness-child-stopped"].includes(v) || /^harness-(?:launch|launched|port|page|acted|caught|closing|closed)-ms-[0-9]+$/.test(v) || /^source-line-[0-9]+$/.test(v) || /^batch-(?:state-(?:pending|unknown|busy|conflict|success|other)|step-(?:both|first|second|removed|conflict|reviewed|verified|closed))$/.test(v))).map(a=>a.description).join(",")); }
  /** @param {import("@playwright/test/reporter").FullResult} result */
  onEnd(result) { console.log("Browser gate: " + result.status); }
  onError() { console.log("Browser harness error."); }
}
