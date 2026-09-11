/** No exception, assertion values, stdout, DOM or attachment is serialized. */
export default class SafeReporter {
  /** @param {import("@playwright/test/reporter").TestCase} test @param {import("@playwright/test/reporter").TestResult} result */
  onTestEnd(test, result) { console.log(test.titlePath().join(" > ") + ": " + result.status + " " + test.annotations.filter(a=>["gate","check"].includes(a.type) && (a.description ?? "").split("|").every(v=>["assertion","roundtrip","three-calls","post-origin","redirect","sink-control","csrf-cors","csrf-form","port","version","action","exit","other","Browser harness failed."].includes(v))).map(a=>a.description).join(",")); }
  /** @param {import("@playwright/test/reporter").FullResult} result */
  onEnd(result) { console.log("Browser gate: " + result.status); }
  onError() { console.log("Browser harness error."); }
}
