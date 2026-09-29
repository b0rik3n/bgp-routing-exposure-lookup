(() => {
  const assets = new URL(".", document.currentScript.src);
  const labels = {mapped: "Mapped", partial: "Partial coverage", multiple_networks: "Multiple networks", ambiguous: "Review origins", as_set: "AS set", multiple_origins: "Multiple origins", not_observed: "Not observed", special_use: "Special use", invalid: "Invalid input", error: "Lookup failed"};
  const icon = (name) => `<svg aria-hidden="true"><use href="${new URL("icons.svg", assets)}#${name}"></use></svg>`;
  class NetworkLookup extends HTMLElement {
    connectedCallback() {
      if (this.root) return;
      this.root = this.attachShadow({mode: "open"});
      this.root.innerHTML = `<link rel="stylesheet" href="${new URL("style.css", assets)}">
        <div class="view-tabs" role="tablist" aria-label="Lookup view"><button role="tab" id="paths-tab" aria-selected="true">Observed BGP paths</button><button role="tab" id="origins-tab" aria-selected="false">Origin mapping</button></div>
        <form><section class="entry"><div><div class="entry-head"><label for="resources">IP addresses &amp; networks</label><div class="row"><button type="button" id="example" title="Load example addresses">Example</button><button type="button" id="import">${icon("upload")}Import file</button><input id="file" type="file" accept=".csv,.txt,.tsv,text/plain,text/csv" hidden></div></div>
        <textarea id="resources" spellcheck="false" placeholder="129.55.110.9&#10;129.55.0.0/24" aria-label="IP addresses, CIDRs, or start-end ranges"></textarea><p class="privacy" id="filename">CSV, TSV, or TXT · Up to 1,000 entries</p></div>
        <div class="configuration"><fieldset><legend>Routing date</legend><div class="mode"><label><input name="mode" type="radio" value="latest" checked><span>Latest</span></label><label><input name="mode" type="radio" value="historical"><span>Historical</span></label></div><div class="date-wrap" hidden><label for="date">Snapshot date (UTC)</label><input id="date" type="date" min="2005-05-09"></div></fieldset><button class="primary" id="resolve" type="submit">${icon("search")}Resolve networks</button><p class="privacy">Inputs stay on the lookup server. No connections are made to imported IPs.</p></div></section></form>
        <div class="notice" id="notice"></div>
        <div id="status" class="status" role="status" aria-live="polite">Ready</div>
        <section id="results" hidden><div class="summary"><div class="metric"><strong id="total">0</strong><span>Imported</span></div><div class="metric mapped"><strong id="mapped">0</strong><span>Mapped</span></div><div class="metric review"><strong id="review">0</strong><span>Review</span></div><div class="metric"><strong id="unmapped">0</strong><span>Unmapped</span></div></div>
        <div class="result-head"><h2>Network attribution</h2><div class="toolbar"><input id="search" type="search" placeholder="Filter results" aria-label="Filter results"><select id="filter" aria-label="Result status"><option value="all">All results</option><option value="mapped">Mapped</option><option value="review">Needs review</option><option value="unmapped">Unmapped</option></select><button id="csv" class="icon" title="Export CSV" aria-label="Export CSV">${icon("download")}</button><button id="json" title="Export JSON">JSON</button></div></div>
        <div class="table-wrap"><table><thead><tr><th>Input / covered range</th><th>Matched BGP prefix</th><th>Origin ASN</th><th>Network organization</th><th>Status</th><th>Routing snapshot</th></tr></thead><tbody id="rows"></tbody></table></div><div id="sources" class="sources"></div><p id="row-count" class="small muted"></p></section>
        <div id="empty" class="empty">${icon("network")}<div>No lookup results</div></div>
        <section id="path-results" hidden><div class="result-head"><h2>Observed paths to origin networks</h2><div class="toolbar"><button id="path-csv" title="Export observed BGP paths as CSV" aria-label="Export observed BGP paths as CSV">${icon("download")}CSV</button><button id="path-json" title="Export observed BGP paths as JSON" aria-label="Export observed BGP paths as JSON">JSON</button></div></div><div id="path-content"></div></section>
        <footer class="footer">Data: <a href="https://stat.ripe.net/docs/data-api/api-endpoints/bgp-state" target="_blank" rel="noreferrer">RIPE RIS paths</a>, <a href="https://www.caida.org/catalog/datasets/as-relationships/" target="_blank" rel="noreferrer">CAIDA AS Relationships</a>, <a href="https://www.caida.org/catalog/datasets/routeviews-prefix2as/" target="_blank" rel="noreferrer">RouteViews prefix-to-AS</a>, and <a href="https://www.caida.org/catalog/datasets/as-organizations/" target="_blank" rel="noreferrer">AS Organizations</a>. Relationship classifications are inferences; collector peer counts are not traffic share.</footer>`;
      const today = new Date().toISOString().slice(0,10);
      this.el("date").max = today;
      this.el("date").value = today;
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
      this.el("example").onclick = () => { this.el("resources").value = this.view==="paths" ? "AS63" : "129.55.110.9\n129.55.0.0/24\n8.8.8.8\n1.1.1.0/24\n2606:4700:4700::1111\n10.0.0.1"; this.el("filename").textContent = "Example input"; };
      this.el("search").oninput = () => this.renderRows();
      this.el("filter").onchange = () => this.renderRows();
      this.el("csv").onclick = () => this.downloadCsv();
      this.el("json").onclick = () => this.download(JSON.stringify(this.payload,null,2), "application/json", "network-lookup.json");
      this.el("path-csv").onclick=()=>this.downloadCsv();
      this.el("path-json").onclick=()=>this.download(JSON.stringify(this.payload,null,2),"application/json","observed-paths.json");
      this.setView("paths");
      this.el("resources").value="AS63";
    }
    disconnectedCallback() { clearTimeout(this.timer); this.controller?.abort(); }
    el(id) { return this.root.getElementById(id); }
    setView(view) {
      this.view=view;
      const paths=view==="paths";
      ["paths","origins"].forEach(name=>{this.el(`${name}-tab`).setAttribute("aria-selected",String(name===view));this.el(`${name}-tab`).tabIndex=name===view?0:-1;});
      this.el("results").hidden=true;this.el("path-results").hidden=true;this.el("empty").hidden=false;
      this.root.querySelector('label[for="resources"]').textContent=paths?"ASN, IP address, or network":"IP addresses & networks";
      this.el("resources").placeholder=paths?"AS63\n129.55.110.9\n129.55.0.0/24":"129.55.110.9\n129.55.0.0/24";
      this.el("resources").setAttribute("aria-label",paths?"ASNs, IP addresses, or CIDRs":"IP addresses, CIDRs, or start-end ranges");
      if (!paths && this.el("resources").value==="AS63") this.el("resources").value="129.55.110.9";
      this.el("resolve").innerHTML=icon("search")+(paths?"Find observed paths":"Resolve networks");
      this.el("filename").textContent=paths?"CSV, TSV, or TXT · Up to 20 entries":"CSV, TSV, or TXT · Up to 1,000 entries";
      this.root.querySelector(".configuration .privacy").textContent=paths?"Public IP, prefix, or ASN queries are sent to RIPE NCC. No connections are made to imported IPs.":"Inputs stay on the lookup server. No connections are made to imported IPs.";
      this.root.querySelector('label[for="date"]').textContent=paths?"Observation date (12:00 UTC)":"Snapshot date (UTC)";
      this.el("notice").textContent=paths?"Observed adjacent ASes appear immediately before the origin AS in RIS paths. Relationships are inferred from separate CAIDA data. These adjacencies represent potential ingress worth investigating; they do not confirm traffic flow, a reachable entry point, a security perimeter, or a vulnerability.":"BGP identifies the announcing network. Its organization may be an ISP, cloud provider, or the organization itself; upstream providers are not inferred in this view.";
      this.status("Ready");
    }
    status(message, error=false, busy=false) { this.el("status").textContent=message; this.el("status").className=`status${error?" error":""}${busy?" busy":""}`; }
    async request(path, options={}) {
      const response = await fetch(this.getAttribute("api-base") + path, {...options, cache:"no-store", signal:this.controller?.signal});
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(payload.error || "Lookup service is unavailable.");
      return payload;
    }
    async lookup() {
      this.controller?.abort();
      clearTimeout(this.timer);
      this.controller = new AbortController();
      this.payload = null;
      this.el("results").hidden = true;
      this.el("path-results").hidden = true;
      this.el("empty").hidden = false;
      const text = this.el("resources").value.trim();
      if (!text) return this.status("Add at least one IP address or network.", true);
      this.setBusy(true);
      this.status("Preparing lookup",false,true);
      try {
        const date = this.root.querySelector('[name="mode"]:checked').value === "latest" ? "latest" : this.el("date").value;
        this.job = await this.request("/jobs", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({text,date,mode:this.view})});
        this.started = Date.now();
        await this.poll();
      } catch(error) { this.status(error.message, true); this.setBusy(false); }
    }
    setBusy(busy) {
      ["resolve","import","example","resources","date","paths-tab","origins-tab"].forEach(id=>this.el(id).disabled=busy);
      this.root.querySelectorAll('[name="mode"]').forEach(input=>input.disabled=busy);
    }
    async poll() {
      try {
        const job = await this.request(`/jobs/${this.job.id}`, {headers:{"X-Job-Token":this.job.token}});
        if (job.state === "failed") throw new Error(job.message);
        if (job.state === "complete") {
          this.payload=job.result;
          if(this.payload.kind==="paths") this.renderPaths(); else this.render();
          this.status("Lookup complete");
          this.setBusy(false);
          return;
        }
        if (Date.now()-this.started > 15*60*1000) throw new Error("Lookup is taking too long. Retry after the source recovers.");
        this.status(job.message,false,true);
        this.timer=setTimeout(() => this.poll(),1500);
      } catch(error) { this.status(error.message,true); this.setBusy(false); }
    }
    category(status) { return status==="mapped"?"mapped":["partial","ambiguous","multiple_networks"].includes(status)?"review":"unmapped"; }
    renderPaths() {
      this.el("empty").hidden=true;this.el("path-results").hidden=false;
      const container=this.el("path-content");container.replaceChildren();
      const node=(tag,text,cls)=>{const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(cls)element.className=cls;return element;};
      const relationshipLabels={provider:"Transit provider",peer:"Peer",customer:"Customer",unknown:"Unknown"};
      for (const result of this.payload.results) {
        const section=node("section",undefined,"path-result");container.append(section);
        section.append(node("p",result.input,"input-label"));
        if(result.error || !result.groups.length) section.append(node("p",result.error||"No paths to an origin were observed for this input.","muted"));
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
                const chain=node("div",undefined,"as-path");path.asns.forEach((asn,index)=>{if(index)chain.append(node("span","→","muted"));const hop=node("span",`AS${asn}`,asn===group.origin?"origin-hop":"");hop.title=result.asns[String(asn)]?.name||"Organization not found";chain.append(hop);});record.append(chain);list.append(record);
              }
              shown=end;more.hidden=shown>=neighbor.paths.length;
            };
            let opened=false;details.addEventListener("toggle",()=>{if(details.open&&!opened){opened=true;appendPaths();}});more.onclick=appendPaths;
            if(neighbor.pathsTruncated)details.append(node("p",`Evidence is limited to ${neighbor.paths.length} path/prefix combinations for this neighbor. Counts include all returned RIS routes.`,"warning"));
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
