(() => {
  const assets = new URL(".", document.currentScript.src);
  const labels = {mapped: "Mapped", partial: "Partial coverage", multiple_networks: "Multiple networks", ambiguous: "Review origins", as_set: "AS set", multiple_origins: "Multiple origins", not_observed: "Not observed", not_requested: "Not requested", special_use: "Special use", invalid: "Invalid input", error: "Lookup failed"};
  const icon = (name) => `<svg aria-hidden="true"><use href="${new URL("icons.svg", assets)}#${name}"></use></svg>`;
  class NetworkLookup extends HTMLElement {
    connectedCallback() {
      if (this.root) return;
      this.root = this.attachShadow({mode: "open"});
      this.root.innerHTML = `<link rel="stylesheet" href="${new URL("style.css", assets)}">
        <div class="view-tabs" role="tablist" aria-label="Lookup view"><button role="tab" id="paths-tab" aria-selected="true">Observed BGP paths</button><button role="tab" id="origins-tab" aria-selected="false">Origin mapping</button></div>
        <form><section class="entry"><div><div class="entry-head"><label for="resources">IP addresses &amp; networks</label><div class="row"><button type="button" id="example" title="Load example addresses">Example</button><button type="button" id="import">${icon("upload")}Import file</button><input id="file" type="file" accept=".csv,.txt,.tsv,text/plain,text/csv" hidden></div></div>
        <textarea id="resources" spellcheck="false" placeholder="193.0.0.1&#10;193.0.0.0/24" aria-label="IP addresses, CIDRs, or start-end ranges"></textarea><p class="privacy" id="filename">CSV, TSV, or TXT · Up to 1,000 entries</p></div>
        <div class="configuration"><fieldset><legend>Routing date</legend><div class="mode"><label><input name="mode" type="radio" value="latest" checked><span>Latest</span></label><label><input name="mode" type="radio" value="historical"><span>Historical</span></label></div><div class="date-wrap" hidden><label for="date">Snapshot date (UTC)</label><input id="date" type="date" min="2005-05-09"></div></fieldset><button class="primary" id="resolve" type="submit">${icon("search")}Resolve networks</button><p class="privacy">Inputs stay on the lookup server. No connections are made to imported IPs.</p></div></section></form>
        <details id="investigation-tools" class="investigation-tools"><summary>Save and compare investigations</summary>
          <p class="muted">Capture observed BGP paths with their evidence, or open a saved ZIP without external queries. Up to 1,000 inputs; origin mapping is not included.</p>
          <div class="toolbar"><button type="button" id="capture">Capture investigation</button><button type="button" id="open-investigation">Open investigation</button><input id="investigation-file" type="file" accept=".zip,application/zip" hidden></div>
          <p class="small muted">Capture uses the inputs and routing date above. Export the ZIP after capture to keep it beyond this session.</p>
          <div class="comparison-dates"><label>Earlier date (12:00 UTC)<input id="compare-before" type="date" min="2005-05-09"></label><label>Later date (12:00 UTC)<input id="compare-after" type="date" min="2005-05-09"></label><button type="button" id="compare-dates">Compare dates</button></div>
        </details>
        <section id="investigation-results" hidden aria-label="Saved investigation"><div class="result-head"><h2>Investigation</h2><div class="toolbar"><button id="bundle-export" type="button">Export investigation ZIP</button><button id="replay-investigation" type="button">Replay saved evidence</button><button id="comparison-export" type="button">Export comparison JSON</button></div></div><div id="investigation-content"></div><label>Inspect snapshot <select id="snapshot-select"></select></label></section>
        <p id="request-count" class="small muted" role="status"></p>
        <p id="request-notice" class="warning" role="alert" hidden></p>
        <div class="notice" id="notice"></div>
        <p id="batch-progress" role="status" hidden></p>
        <p id="result-completeness" class="warning" role="status" hidden></p>
        <button id="cancel-job" type="button" hidden>Cancel lookup</button>
        <div id="status" class="status" role="status" aria-live="polite">Ready</div>
        <section id="results" hidden><div class="summary"><div class="metric"><strong id="total">0</strong><span>Imported</span></div><div class="metric mapped"><strong id="mapped">0</strong><span>Mapped</span></div><div class="metric review"><strong id="review">0</strong><span>Review</span></div><div class="metric"><strong id="unmapped">0</strong><span>Unmapped</span></div></div>
        <div class="result-head"><h2>Network attribution</h2><div class="toolbar"><input id="search" type="search" placeholder="Filter results" aria-label="Filter results"><select id="filter" aria-label="Result status"><option value="all">All results</option><option value="mapped">Mapped</option><option value="review">Needs review</option><option value="unmapped">Unmapped</option></select><button id="csv" class="icon" title="Export CSV" aria-label="Export CSV">${icon("download")}</button><button id="json" title="Export JSON">JSON</button></div></div>
        <div class="table-wrap"><table><thead><tr><th>Input / covered range</th><th>Matched BGP prefix</th><th>Origin ASN</th><th>Network organization</th><th>Status</th><th>Routing snapshot</th></tr></thead><tbody id="rows"></tbody></table></div><div id="sources" class="sources"></div><p id="row-count" class="small muted"></p></section>
        <div id="empty" class="empty">${icon("network")}<div>No lookup results</div></div>
        <section id="path-results" hidden><div class="result-head"><h2>Observed paths to origin networks</h2><div class="toolbar"><button id="path-csv" title="Export observed BGP paths as CSV" aria-label="Export observed BGP paths as CSV">${icon("download")}CSV</button><button id="path-json" title="Export observed BGP paths as JSON" aria-label="Export observed BGP paths as JSON">JSON</button></div></div><p class="small muted">Observed routing advertisements—not measured traffic paths. Collector and peer counts describe visibility, not confidence or traffic share. Relationships are separately inferred; an adjacency does not confirm an entry point or vulnerability.</p><div id="path-content"></div></section>
        <footer class="footer">Data: <a href="https://stat.ripe.net/docs/data-api/api-endpoints/bgp-state" target="_blank" rel="noreferrer">RIPE RIS paths</a>, <a href="https://www.caida.org/catalog/datasets/as-relationships/" target="_blank" rel="noreferrer">CAIDA AS Relationships</a>, <a href="https://www.caida.org/catalog/datasets/routeviews-prefix2as/" target="_blank" rel="noreferrer">RouteViews prefix-to-AS</a>, and <a href="https://www.caida.org/catalog/datasets/as-organizations/" target="_blank" rel="noreferrer">AS Organizations</a>. Relationship classifications are inferences; collector peer counts are not traffic share.</footer>`;
      const today = new Date().toISOString().slice(0,10);
      this.el("date").max = today;
      this.el("date").value = today;
      ["compare-before", "compare-after"].forEach(id=>this.el(id).max=today);
      this.el("compare-after").value=today;
      this.el("capture").onclick=()=>this.lookup("investigation");
      this.el("compare-dates").onclick=()=>this.lookup("comparison");
      this.el("open-investigation").onclick=()=>this.el("investigation-file").click();
      this.el("investigation-file").onchange=()=>this.openInvestigation();
      this.el("bundle-export").onclick=()=>this.exportBundle();
      this.el("replay-investigation").onclick=()=>this.replayInvestigation();
      this.el("comparison-export").onclick=()=>this.download(JSON.stringify({createdAt:this.investigation.createdAt,tool:this.investigation.tool,coverageMeaning:this.investigation.coverageMeaning,comparison:this.investigation.comparison},null,2),"application/json","routing-comparison.json");
      this.el("snapshot-select").onchange=()=>this.showSnapshot();
      this.el("cancel-job").onclick=()=>this.cancelLookup();
      this.refreshRequests();this.requestTimer=setInterval(()=>this.refreshRequests(),5000);
      this.refreshAccess();this.accessTimer=setInterval(()=>this.refreshAccess(),10000);
      this.el("paths-tab").onclick=()=>this.setView("paths");
      this.el("origins-tab").onclick=()=>this.setView("origins");
      ["paths-tab","origins-tab"].forEach(id=>this.el(id).onkeydown=(event)=>{
        if (["ArrowLeft","ArrowRight"].includes(event.key)) {event.preventDefault();this.setView(this.view==="paths"?"origins":"paths");this.el(`${this.view}-tab`).focus();}
      });
      this.root.querySelector("form").addEventListener("submit", (event) => {event.preventDefault(); this.lookup();});
      this.root.querySelectorAll('[name="mode"]').forEach(radio => radio.addEventListener("change", () => {
        const historical = this.root.querySelector('[name="mode"]:checked').value === "historical";
        this.root.querySelector(".date-wrap").hidden = !historical;
        this.el("date").required = historical;
      }));
      this.el("import").onclick = () => this.el("file").click();
      this.el("file").onchange = async () => {
        const file = this.el("file").files[0];
        if (!file) return;
        if (file.size > 262144) return this.status("Import must be at most 256 KB.", true);
        try { this.el("resources").value = await file.text(); this.el("filename").textContent = file.name; this.status("File loaded"); }
        catch { this.status("File could not be read.", true); }
      };
      this.el("example").onclick = () => { this.el("resources").value = this.view==="paths" ? "AS3333" : "193.0.0.1\n193.0.0.0/24\n8.8.8.8\n1.1.1.0/24\n2606:4700:4700::1111\n10.0.0.1"; this.el("filename").textContent = "Example input"; };
      this.el("search").oninput = () => this.renderRows();
      this.el("filter").onchange = () => this.renderRows();
      this.el("csv").onclick = () => this.downloadCsv();
      this.el("json").onclick = () => this.download(JSON.stringify(this.payload,null,2), "application/json", "network-lookup.json");
      this.el("path-csv").onclick=()=>this.downloadCsv();
      this.el("path-json").onclick=()=>this.download(JSON.stringify(this.payload,null,2),"application/json","observed-paths.json");
      this.setView("paths");
      this.el("resources").value="AS3333";
    }
    disconnectedCallback() { clearInterval(this.requestTimer); clearInterval(this.accessTimer); clearTimeout(this.timer); this.controller?.abort(); }
    el(id) { return this.root.getElementById(id); }
    async refreshAccess() {
      try {
        const response=await fetch(this.getAttribute("api-base")+"/access",{cache:"no-store"});
        if(!response.ok)throw new Error();
        const data=await response.json();
        for(const source of data.sources||[]) {
          const element=document.querySelector(`.access-indicator[data-source="${source.id}"]`);
          if(!element)continue;
          element.className=`access-indicator ${source.state}`;
          const status=source.state==="available"?"available":source.state==="unavailable"?"unavailable":"checking";
          element.title=`${source.label}: ${status}${source.detail?` (${source.detail})`:""}`;
        }
      } catch {
        document.querySelectorAll(".access-indicator").forEach(element=>{element.className="access-indicator unavailable";element.title="Local server access check unavailable";});
      }
    }
    setView(view) {
      this.view=view;
      this.el("investigation-tools").hidden=view!=="paths";
      this.el("investigation-results").hidden=true;
      this.investigation=null;this.bundleBlob=null;this.job=null;this.payload=null;
      const paths=view==="paths";
      ["paths","origins"].forEach(name=>{this.el(`${name}-tab`).setAttribute("aria-selected",String(name===view));this.el(`${name}-tab`).tabIndex=name===view?0:-1;});
      this.el("results").hidden=true;this.el("path-results").hidden=true;this.el("empty").hidden=false;
      this.root.querySelector('label[for="resources"]').textContent=paths?"ASN, IP address, or network":"IP addresses & networks";
      this.el("resources").placeholder=paths?"AS3333\n193.0.0.1\n193.0.0.0/24":"193.0.0.1\n193.0.0.0/24";
      this.el("resources").setAttribute("aria-label",paths?"ASNs, IP addresses, or CIDRs":"IP addresses, CIDRs, or start-end ranges");
      if (!paths && this.el("resources").value==="AS3333") this.el("resources").value="193.0.0.1";
      this.el("resolve").innerHTML=icon("search")+(paths?"Find observed paths":"Resolve networks");
      this.el("filename").textContent=paths?"CSV, TSV, or TXT · Up to 1,000 entries":"CSV, TSV, or TXT · Up to 1,000 entries";
      this.root.querySelector(".configuration .privacy").textContent=paths?"Public IP, prefix, or ASN queries are sent to RIPE NCC. No connections are made to imported IPs.":"Inputs stay on the lookup server. No connections are made to imported IPs.";
      this.root.querySelector('label[for="date"]').textContent=paths?"Observation date (12:00 UTC)":"Snapshot date (UTC)";
      this.el("notice").textContent=paths?"Observed adjacent ASes appear immediately before the origin AS in RIS paths. Relationships are inferred from separate CAIDA data. These adjacencies represent potential ingress worth investigating; they do not confirm traffic flow, a reachable entry point, a security perimeter, or a vulnerability.":"BGP identifies the announcing network. Its organization may be an ISP, cloud provider, or the organization itself; upstream providers are not inferred in this view.";
      this.status("Ready");
    }
    status(message, error=false, busy=false) { this.el("status").textContent=message; this.el("status").className=`status${error?" error":""}${busy?" busy":""}`; }
    showProgress(value) {
      const element=this.el("batch-progress");
      element.hidden=!value;
      if(!value)return;
      const snapshot=value.snapshot?`Snapshot ${value.snapshot} of ${value.snapshots} (${value.date}) · `:"";
      element.textContent=`${snapshot}${value.processed} of ${value.total} processed · ${value.completed} completed · ${value.failed} failed · ${value.skipped} special-use skipped · ${value.remaining} remaining${value.notRequested?` (${value.notRequested} not requested)`:""}${value.current?` · Current: ${value.current}`:""}`;
    }
    showCompleteness() {
      const results=this.payload.results;
      const failed=results.filter(r=>["error","invalid"].includes(r.status)).length;
      const pending=results.filter(r=>r.status==="not_requested").length;
      const skipped=results.filter(r=>r.status==="special_use").length;
      const warned=results.filter(r=>r.warnings?.length).length;
      const truncated=results.filter(r=>r.groups?.some(g=>g.neighbors.some(n=>n.pathsTruncated))).length;
      const partial=results.filter(r=>r.status==="partial").length;
      const completed=results.length-failed-pending-skipped;
      const element=this.el("result-completeness");element.hidden=false;
      const needsReview=failed||pending||warned||truncated||partial||this.payload.incomplete;
      element.className=needsReview?"warning":"small muted";
      element.textContent=`${needsReview?"Results need review. ":""}${completed} completed · ${failed} failed/invalid · ${pending} not requested · ${skipped} special-use skipped. ${warned} inputs with warnings · ${truncated} with truncated path evidence · ${partial} with partial coverage. `+
        (this.payload.incomplete?`Stopped: ${this.payload.incomplete} `:"")+
        (failed||pending?"Export completed results, then retry failed or unprocessed inputs. ":"")+
        (truncated?"Displayed path evidence is limited; narrow the target to investigate further. ":"")+
        (warned?"Review per-input warnings for unavailable data or excluded observations. ":"");
    }
    async request(path, options={}) {
      const response = await fetch(this.getAttribute("api-base") + path, {...options, cache:"no-store", signal:this.controller?.signal});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || "Lookup service is unavailable.");
      return payload;
    }
    async lookup(researchMode=null) {
      this.controller?.abort();
      clearTimeout(this.timer);
      this.controller = new AbortController();
      this.job=null;this.el("cancel-job").hidden=true;
      this.payload = null;
      this.showProgress(null);this.el("result-completeness").hidden=true;
      this.investigation=null;this.bundleBlob=null;
      this.el("investigation-results").hidden=true;
      this.el("path-csv").hidden=false;
      this.el("results").hidden = true;
      this.el("path-results").hidden = true;
      this.el("empty").hidden = false;
      const text = this.el("resources").value.trim();
      if (!text) return this.status("Add at least one IP address or network.", true);
      this.setBusy(true);
      this.status("Preparing lookup",false,true);
      try {
        let date = this.root.querySelector('[name="mode"]:checked').value === "latest" ? "latest" : this.el("date").value;
        let comparisonDate;
        if(researchMode==="comparison") {
          date=this.el("compare-before").value;comparisonDate=this.el("compare-after").value;
          if(!date||!comparisonDate||date>=comparisonDate) throw new Error("Choose an earlier and a later historical date.");
        }
        this.job = await this.request("/jobs", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({text,date,mode:researchMode?"investigation":this.view,comparisonDate})});
        this.el("cancel-job").hidden=false;this.el("cancel-job").disabled=false;
        this.started = Date.now();
        await this.poll();
      } catch(error) { this.status(error.message, true); this.setBusy(false); }
    }
    async refreshRequests() {
      try {
        const response=await fetch(this.getAttribute("api-base")+"/requests",{cache:"no-store"});
        if(!response.ok)throw new Error("Counter unavailable");
        const info=await response.json();
        this.el("request-count").textContent=`RIPE requests today (UTC): ${info.usedToday.toLocaleString()} · ${info.intervalSeconds}s pause · one at a time · no daily cap`;
        const notice=this.el("request-notice");notice.hidden=!info.registrationNotice;
        if(info.registrationNotice && this.noticeDay!==info.day) {
          this.noticeDay=info.day;
          notice.replaceChildren(document.createTextNode("1,000 RIPE requests reached today. Lookups will continue. RIPE asks you to register if you regularly exceed 1,000 requests/day. "));
          const link=document.createElement("a");link.textContent="RIPE usage guidance";link.href="https://data.stat.ripe.net/docs/data-api/ripestat-data-api#rules-of-usage";link.target="_blank";link.rel="noreferrer";notice.append(link);
        }
      } catch {this.el("request-count").textContent="RIPE request counter unavailable.";}
    }
    async cancelLookup() {
      if(!this.job)return;
      this.el("cancel-job").disabled=true;
      try {await this.request(`/jobs/${this.job.id}/cancel`,{method:"POST",headers:{"X-Job-Token":this.job.token}});this.status("Cancelling. An in-flight request may finish; completed results will remain available.");}
      catch(error){this.status(error.message,true);this.el("cancel-job").disabled=false;}
    }
    setBusy(busy) {
      if(!busy)this.el("cancel-job").hidden=true;
      ["resolve","import","example","resources","date","paths-tab","origins-tab","capture","compare-dates","compare-before","compare-after","open-investigation","replay-investigation","bundle-export","comparison-export","snapshot-select"].forEach(id=>this.el(id).disabled=busy);
      this.root.querySelectorAll('[name="mode"]').forEach(input=>input.disabled=busy);
    }
    async poll() {
      try {
        const job = await this.request(`/jobs/${this.job.id}`, {headers:{"X-Job-Token":this.job.token}});
        this.showProgress(job.progress);
        if (job.state === "failed") throw new Error(job.message);
        if (job.state === "cancelled" && !job.result) {this.status(job.message);this.setBusy(false);return;}
        if (job.state === "complete" || job.state === "cancelled") {
          if(job.result.kind==="investigation") {
            this.investigation=job.result;this.renderInvestigation();
            this.status(job.state==="cancelled"?"Cancellation arrived after the investigation finished; the complete ZIP is available.":"Investigation captured. Export the ZIP to retain its evidence.");this.setBusy(false);return;
          }
          this.payload=job.result;
          if(this.payload.kind==="paths") this.renderPaths(); else this.render();
          this.status(job.state==="cancelled"?"Cancelled. Export any completed results before leaving.":this.payload.incomplete?`Partial results: ${this.payload.incomplete}`:"Processing finished. Review the result summary below.");
          this.setBusy(false);
          return;
        }
        this.status(job.message,false,true);
        this.timer=setTimeout(() => this.poll(),1500);
      } catch(error) { this.status(error.message,true); this.setBusy(false); }
    }
    async bundle() {
      if(this.bundleBlob) return this.bundleBlob;
      if(!this.job) throw new Error("No investigation is open.");
      const response=await fetch(`${this.getAttribute("api-base")}/jobs/${this.job.id}/bundle`,{headers:{"X-Job-Token":this.job.token},cache:"no-store"});
      if(!response.ok) throw new Error("Bundle expired or unavailable. Capture the investigation again.");
      this.bundleBlob=await response.blob();return this.bundleBlob;
    }
    async exportBundle() {
      try {this.download(await this.bundle(),"application/zip","routing-investigation.zip");}
      catch(error) {this.status(error.message,true);}
    }
    async openInvestigation() {
      const file=this.el("investigation-file").files[0];this.el("investigation-file").value="";
      if(!file) return;
      if(file.size>32000000) return this.status("Investigation ZIP must be at most 32 MB.",true);
      this.setBusy(true);this.status("Checking bundle integrity and replaying saved evidence",false,true);
      try {
        const value=await this.request("/investigations/open",{method:"POST",headers:{"Content-Type":"application/zip"},body:file});
        this.showProgress(null);this.job=null;this.bundleBlob=file;this.investigation=value;
        this.renderInvestigation();this.status("Saved investigation opened. No external queries were made.");
      } catch(error) {this.status(error.message,true);} finally {this.setBusy(false);}
    }
    async replayInvestigation() {
      this.setBusy(true);this.status("Reprocessing saved evidence without external queries",false,true);
      try {
        this.investigation=await this.request("/investigations/replay",{method:"POST",headers:{"Content-Type":"application/zip"},body:await this.bundle()});
        this.renderInvestigation();this.status("Replay finished. Review per-input checks below.");
      } catch(error) {this.status(error.message,true);} finally {this.setBusy(false);}
    }
    showSnapshot() {
      this.payload=this.investigation.snapshots[Number(this.el("snapshot-select").value)||0];
      this.el("results").hidden=true;
      this.el("path-csv").hidden=true;
      this.renderPaths();
    }
    renderInvestigation() {
      const data=this.investigation,container=this.el("investigation-content");container.replaceChildren();
      this.el("investigation-results").hidden=false;
      this.el("comparison-export").hidden=!data.comparison;
      const node=(tag,text,cls)=>{const el=document.createElement(tag);if(text!==undefined)el.textContent=text;if(cls)el.className=cls;return el;};
      container.append(node("p",`Captured ${data.createdAt} · ${data.inputs.length} input(s)`));
      container.append(node("p",data.limitation,"small muted"));
      const version=node("details");version.append(node("summary","Provenance and replay scope"),node("pre",JSON.stringify(data.tool,null,2)),node("p",data.integrityMeaning,"small muted"),node("p",`Processing code matches capture: ${data.sameProcessingCode?"yes":"no; results use the currently installed processor"}. Saved comparison replay: ${data.comparisonReplay}.`),node("pre",JSON.stringify(data.replayTool,null,2)));container.append(version);
      const select=this.el("snapshot-select");select.replaceChildren();
      data.snapshots.forEach((snapshot,index)=>{
        const option=node("option",`${index+1}: ${snapshot.requestedDate}`);option.value=String(index);select.append(option);
        const checks=data.replay[index];
        container.append(node("p",`Snapshot ${index+1} replay: ${checks.filter(c=>c.status==="match").length} matched; ${checks.filter(c=>c.status==="mismatch").length} mismatched; ${checks.filter(c=>c.status==="unavailable").length} unavailable.`));
        const details=node("details");details.append(node("summary","Per-input replay checks"));checks.forEach(check=>details.append(node("p",`${check.input}: ${check.status}${check.reason?" — "+check.reason:""}`)));container.append(details);
      });
      if(data.comparison) {
        container.append(node("h3","Two-date comparison"),node("p","Newly observed does not prove a new connection; not seen does not prove removal. These snapshots do not show changes between the two observation times.","warning"),node("p",data.coverageMeaning,"small muted"));
        for(const result of data.comparison) {
          const section=node("section",undefined,"comparison-result");container.append(section);
          section.append(node("h4",result.input));
          if(result.status!=="compared") {section.append(node("p",result.reason,"warning"));continue;}
          section.append(node("p",`${result.beforeObservedAt} → ${result.afterObservedAt}`));
          section.append(node("p",`Reporting peers: ${result.coverage.before.length} → ${result.coverage.after.length}; ${result.coverage.common.length} common; ${result.coverage.added.length} newly reporting; ${result.coverage.notSeen.length} no longer reporting.`));
          const coverage=node("details");coverage.append(node("summary","Inspect collector-peer coverage"),node("pre",JSON.stringify(result.coverage,null,2)));section.append(coverage);
          for(const [label,changes] of [["All observations",result.allChanges],["Common reporting peers",result.commonPeerChanges],["Relationship inferences",result.relationshipChanges]]) {
            const details=node("details");details.append(node("summary",`${label}${changes?" · "+changes.length+" changes":" · unavailable"}`));section.append(details);
            if(!changes) {details.append(node("p","No common reporting peers; a restricted comparison cannot be made."));continue;}
            if(!changes.length) {details.append(node("p","No differences in the comparable evidence. This does not prove the network was unchanged."));continue;}
            let shown=0;const more=node("button","Show more changes");more.type="button";
            const append=()=>{for(const change of changes.slice(shown,shown+50)) {
              const row=node("div",undefined,"path-record");row.append(node("strong",change.change),node("p",`${change.prefix} · AS${change.neighbor} → AS${change.origin}`));
              if(change.before!==undefined) row.append(node("p",`${change.before} → ${change.after}`));
              else {const evidence=node("details");evidence.append(node("summary","Paths and observers before / after"),node("pre",JSON.stringify(change,null,2)));row.append(evidence);}
              details.insertBefore(row,more);
            }shown+=50;more.hidden=shown>=changes.length;};
            details.append(more);more.onclick=append;let loaded=false;details.ontoggle=()=>{if(details.open&&!loaded){loaded=true;append();}};
          }
          section.append(node("p",`CAIDA relationship dates: ${result.relationshipDates.map(d=>d||"unavailable").join(" → ")}. Direct-origin observations: ${result.beforeDirectOriginObservations} → ${result.afterDirectOriginObservations}.`,"small muted"));
          result.warnings.forEach(w=>section.append(node("p",w,"warning")));
        }
      }
      this.showSnapshot();
    }
    category(status) { return status==="mapped"?"mapped":["partial","ambiguous","multiple_networks"].includes(status)?"review":"unmapped"; }
    renderPaths() {
      this.showCompleteness();
      this.el("empty").hidden=true;this.el("path-results").hidden=false;
      const container=this.el("path-content");container.replaceChildren();
      const node=(tag,text,cls)=>{const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(cls)element.className=cls;return element;};
      const relationshipLabels={provider:"Transit provider",peer:"Peer",customer:"Customer",unknown:"Unknown"};
      for (const result of this.payload.results) {
        const section=node("section",undefined,"path-result");container.append(section);
        section.append(node("p",`${result.input} · ${labels[result.status]||result.status}`,"input-label"));
        if(result.error || !result.groups.length) section.append(node("p",result.error||"No paths to an origin were observed for this input.",result.error?"warning":"muted"));
        for(const warning of result.warnings) section.append(node("p",warning,"warning"));
        for(const group of result.groups) {
          const org=result.asns[String(group.origin)]?.name||"Organization not found";
          section.append(node("h3",`AS${group.origin} · ${org}`));
          section.append(node("p",`${group.neighbors.length} observed adjacent ASes · ${group.collectors.length} RIS collectors · ${group.peerCount} distinct collector peers`,"small muted"));
          const wrapper=node("div",undefined,"table-wrap paths-table");const table=node("table");wrapper.append(table);section.append(wrapper);
          const thead=node("thead"),heading=node("tr");["Observed adjacent AS","Relationship (inferred)","RIS peers","Collectors","Observed adjacency"].forEach(text=>heading.append(node("th",text)));thead.append(heading);table.append(thead);
          const tbody=node("tbody");table.append(tbody);
          for(const neighbor of group.neighbors) {
            const row=node("tr");tbody.append(row);
            const identity=node("td",undefined,"provider");identity.append(node("strong",result.asns[String(neighbor.asn)]?.name||"Organization not found"),node("span",`AS${neighbor.asn} · ${result.asns[String(neighbor.asn)]?.asName||""}`,"sub"));row.append(identity);
            const rel=node("td");rel.append(node("span",relationshipLabels[neighbor.relationship],`badge ${neighbor.relationship==="provider"?"mapped":neighbor.relationship==="unknown"?"neutral":"review"}`));row.append(rel);
            row.append(node("td",String(neighbor.peerCount)),node("td",String(neighbor.collectors.length)),node("td",`AS${neighbor.asn} → AS${group.origin}`,"asn"));
            const evidenceRow=node("tr"),cell=node("td");cell.colSpan=5;cell.className="evidence-cell";evidenceRow.append(cell);tbody.append(evidenceRow);
            const details=node("details");details.append(node("summary",`${neighbor.pathCount} observed path/prefix combinations · ${neighbor.prefixes.length} prefixes`));cell.append(details);
            const list=node("div",undefined,"path-list");details.append(list);let shown=0;
            const more=node("button","Show more paths");more.type="button";details.append(more);
            const appendPaths=()=>{
              const end=Math.min(shown+20,neighbor.paths.length);
              for(const path of neighbor.paths.slice(shown,end)) {
                const record=node("div",undefined,"path-record");record.append(node("div",`${path.prefix} · ${path.peerCount} collector peers · ${path.collectors.join(", ")}`,"small muted"));
                const chain=node("div",undefined,"as-path");
                path.asns.forEach((asn,index)=>{
                  if(index)chain.append(node("span","→","muted"));
                  const info=result.asns[String(asn)]||{};
                  const names=[...new Set([info.asName,info.name].filter(Boolean))];
                  const label=names.length?names.join(" · "):"Name unavailable";
                  const country=info.country?`, ${info.country}`:"";
                  chain.append(node("span",`AS${asn} — ${label}${country}`,`as-hop${asn===group.origin?" origin-hop":""}`));
                });
                record.append(chain);list.append(record);
              }
              shown=end;more.hidden=shown>=neighbor.paths.length;
            };
            let opened=false;details.addEventListener("toggle",()=>{if(details.open&&!opened){opened=true;appendPaths();}});more.onclick=appendPaths;
            if(neighbor.pathsTruncated)cell.append(node("p",`Evidence is limited to ${neighbor.paths.length} path/prefix combinations for this neighbor. Counts include all returned RIS routes.`,"warning"));
          }
          if(!group.neighbors.length){const row=node("tr"),cell=node("td","Only direct origin observations were available; no observed adjacent AS can be identified.");cell.colSpan=5;row.append(cell);tbody.append(row);}
        }
        const sources=node("div",undefined,"sources");section.append(sources);
        const source=(entry,label)=>{if(!entry)return;const a=node("a",label);if(!/^https:\/\/(?:stat\.ripe\.net\/data\/bgp-state\/|publicdata\.caida\.org\/datasets\/)/.test(entry.url))return;a.href=entry.url;a.target="_blank";a.rel="noreferrer";sources.append(a);};
        source(result.observation,`RIS observation: ${result.observation?.observedAt.replace("T"," ")} UTC`);
        source(result.relationships,`Relationships: ${result.relationships?.snapshotDate}`);
        source(result.organizations,`Organization names: ${result.organizations?.snapshotDate}`);
      }
    }
    render() {
      this.showCompleteness();
      this.el("empty").hidden=true;
      this.el("results").hidden=false;
      const counts={mapped:0,review:0,unmapped:0};
      this.payload.results.forEach(result => counts[this.category(result.status)]++);
      this.el("total").textContent=this.payload.results.length;
      Object.entries(counts).forEach(([key,value]) => this.el(key).textContent=value);
      this.renderRows();
      this.el("sources").replaceChildren();
      const sources=new Map();
      this.payload.results.forEach(result => {
        if (result.routing) sources.set(result.routing.url, `${result.routing.collector}: ${result.routing.snapshotAt.replace("T"," ").replace("+00:00"," UTC")}`);
        if (result.organizations) sources.set(result.organizations.url, `Organization names: ${result.organizations.snapshotDate}`);
      });
      for (const [url,label] of sources) {
        const a=document.createElement("a");
        if (!url.startsWith("https://publicdata.caida.org/datasets/")) continue;
        a.href=url; a.textContent=label; a.target="_blank"; a.rel="noreferrer";
        this.el("sources").append(a);
      }
    }
    renderRows() {
      if (!this.payload) return;
      const tbody=this.el("rows"); tbody.replaceChildren();
      const query=this.el("search").value.toLowerCase();
      const filter=this.el("filter").value;
      let visible=0,total=0;
      const fragment=document.createDocumentFragment();
      for (const result of this.payload.results) {
        const segments=result.segments.length?result.segments:[{}];
        total+=segments.length;
        if (filter!=="all" && this.category(result.status)!==filter) continue;
        for (const segment of segments) {
          const origins=segment.origins||[];
          const haystack=[result.input,segment.prefix,...origins.flatMap(origin=>[origin.name,`AS${origin.asn}`])].join(" ").toLowerCase();
          if (!haystack.includes(query)) continue;
          visible++;
          if (visible>500) continue;
          const tr=document.createElement("tr");
          const cell=(value,cls,sub)=>{const td=document.createElement("td");td.className=cls;td.textContent=value;if(sub){const detail=document.createElement("span");detail.className="sub";detail.textContent=sub;td.append(detail);}tr.append(td);return td;};
          const range=segment.start && (segment.start!==segment.end || result.segments.length>1)?`${segment.start} - ${segment.end}`:result.note;
          cell(result.input,"input",range);
          cell(segment.prefix||"--","prefix");
          cell(origins.map(o=>`AS${o.asn}`).join(", ")||"--","asn");
          cell(origins.map(o=>o.name||"Organization not found").join(" / ")||"--","provider",result.error);
          const status=segment.status==="mapped" && result.status==="multiple_networks" ? "multiple_networks" : segment.status||result.status;
          const td=cell("","status-cell"); const badge=document.createElement("span");
          badge.className="badge "+(status==="mapped"?"mapped":["as_set","multiple_origins","multiple_networks"].includes(status)?"review":["invalid","error"].includes(status)?"error":"neutral");
          badge.textContent=labels[status]||status;td.append(badge);
          cell(result.routing?.snapshotAt.slice(0,10)||"--","date");
          fragment.append(tr);
        }
      }
      tbody.append(fragment);
      if (!visible) {const tr=document.createElement("tr"),td=document.createElement("td");td.colSpan=6;td.textContent="No matching results";tr.append(td);tbody.append(tr);}
      this.el("row-count").textContent=visible>500?`Showing 500 of ${visible.toLocaleString()} matching segments. Export includes all ${total.toLocaleString()} segments.`:`${visible.toLocaleString()} of ${total.toLocaleString()} segments`;
    }
    download(data,type,name) {const url=URL.createObjectURL(new Blob([data],{type}));const a=document.createElement("a");a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
    async downloadCsv() {
      try {
        const response=await fetch(`${this.getAttribute("api-base")}/jobs/${this.job.id}/export`,{headers:{"X-Job-Token":this.job.token},cache:"no-store"});
        if(!response.ok) throw new Error("Export expired or unavailable. Run the lookup again.");
        this.download(await response.text(),"text/csv",this.payload.kind==="paths"?"observed-paths.csv":"network-lookup.csv");
      } catch(error) {this.status(error.message,true);}
    }
  }
  if (!customElements.get("network-lookup")) customElements.define("network-lookup",NetworkLookup);
})();
