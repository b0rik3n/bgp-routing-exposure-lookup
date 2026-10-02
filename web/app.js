(() => {
  const assets = new URL(".", document.currentScript.src);
  const labels = {mapped: "Mapped", partial: "Partial coverage", multiple_networks: "Multiple networks", ambiguous: "Review origins", as_set: "AS set", multiple_origins: "Multiple origins", not_observed: "Not observed", not_requested: "Not requested", special_use: "Special use", invalid: "Invalid input", error: "Lookup failed"};
  const icon = (name) => `<svg aria-hidden="true"><use href="${new URL("icons.svg", assets)}#${name}"></use></svg>`;
  class NetworkLookup extends HTMLElement {
    connectedCallback() {
      if (this.root) return;
      this.root = this.attachShadow({mode: "open"});
      this.root.innerHTML = `<link rel="stylesheet" href="${new URL("style.css?revision=map-controls-1", assets)}">
        <div class="view-tab-bar"><div class="view-tabs" role="tablist" aria-label="Lookup view"><button role="tab" id="paths-tab" aria-selected="true">Observed BGP paths</button><button role="tab" id="origins-tab" aria-selected="false">Origin mapping</button><button role="tab" id="live-tab" aria-selected="false">Live RIS View</button></div><label class="theme-picker" for="theme"><span>Theme</span><select id="theme" title="Theme is saved only in this browser"><option value="soc">SOC Dark</option><option value="nord">Nord Calm</option><option value="contrast">High Contrast</option><option value="matrix">Matrix</option><option value="mucaro">Mucaro Dusk</option><option value="notebook">Field Notebook</option><option value="amber">Terminal Amber</option></select></label></div>
        <form><section class="entry"><div><div class="entry-head"><label for="resources">IP addresses &amp; networks</label><div class="row"><button type="button" id="example" title="Load example addresses">Load example</button><button type="button" id="import">${icon("upload")}Import file</button><input id="file" type="file" accept=".csv,.txt,.tsv,text/plain,text/csv" hidden></div></div>
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
        <div class="result-head"><h2>Network attribution</h2><div class="toolbar"><input id="search" type="search" placeholder="Filter results" aria-label="Filter results"><select id="filter" aria-label="Result status"><option value="all">All results</option><option value="mapped">Mapped</option><option value="review">Needs review</option><option value="unmapped">Unmapped</option></select><button id="csv" class="icon" title="Export CSV" aria-label="Export CSV">${icon("download")}</button><button id="json" title="Export JSON">Export JSON</button></div></div>
        <div class="table-wrap"><table><thead><tr><th>Input / covered range</th><th>Matched BGP prefix</th><th>Origin ASN</th><th>Network organization</th><th>Status</th><th>Routing snapshot</th></tr></thead><tbody id="rows"></tbody></table></div><div id="sources" class="sources"></div><p id="row-count" class="small muted"></p></section>
        <div id="empty" class="empty">${icon("network")}<div>No lookup results</div></div>
        <section id="path-results" hidden><div class="result-head"><h2>Observed paths to origin networks</h2><div class="toolbar"><button id="path-csv" title="Export observed BGP paths as CSV" aria-label="Export observed BGP paths as CSV">${icon("download")}CSV</button><button id="path-json" title="Export observed BGP paths as JSON">Export JSON</button></div></div><p class="small muted">Observed routing advertisements—not measured traffic paths. Collector and peer counts describe visibility, not confidence or traffic share. Relationships are separately inferred; an adjacency does not confirm an entry point or vulnerability.</p><div id="path-content"></div></section>
        <section id="live-view" class="live-view" hidden aria-label="Live RIS View"><div class="result-head"><div><h2>Live RIS View</h2><p class="small muted">A temporary stream of public BGP updates observed by RIPE RIS.</p></div><div class="toolbar"><button type="button" id="live-start" class="primary">Start live view</button><button type="button" id="live-stop" hidden>Stop</button></div></div><div class="live-configuration"><label for="live-asn">AS number<input id="live-asn" inputmode="numeric" autocomplete="off" spellcheck="false" placeholder="3333" value="3333" aria-describedby="live-privacy"></label><label for="live-role">Match updates where<select id="live-role"><option value="origin">This AS is the origin</option><option value="path">This AS appears anywhere in the path</option></select></label></div><p id="live-privacy" class="privacy">Starting opens a direct connection from this browser to RIPE RIS. RIPE can observe the selected AS filter and your public IP address. Events stay in browser memory and are cleared when you stop.</p><p id="live-status" class="status" role="status" aria-live="polite">Ready to start a live view.</p><p class="small muted">Live observations do not establish traffic flow, reachability, a security incident, or a policy violation.</p><div id="live-events" class="live-events" aria-live="polite"><p class="muted">No live events yet.</p></div></section>
        <footer class="footer">Data: <a href="https://stat.ripe.net/docs/data-api/api-endpoints/bgp-state" target="_blank" rel="noreferrer">RIPE RIS paths</a>, <a href="https://www.caida.org/catalog/datasets/as-relationships/" target="_blank" rel="noreferrer">CAIDA AS Relationships</a>, <a href="https://www.caida.org/catalog/datasets/routeviews-prefix2as/" target="_blank" rel="noreferrer">RouteViews prefix-to-AS</a>, and <a href="https://www.caida.org/catalog/datasets/as-organizations/" target="_blank" rel="noreferrer">AS Organizations</a>. Relationship classifications are inferences; collector peer counts are not traffic share.</footer>`;
      const today = new Date().toISOString().slice(0,10);
      this.el("date").max = today;
      this.el("date").value = today;
      ["compare-before", "compare-after"].forEach(id=>this.el(id).max=today);
      this.el("compare-after").value=today;
      this.applyTheme(this.savedTheme());
      this.el("theme").onchange=()=>this.applyTheme(this.el("theme").value);
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
      this.el("live-tab").onclick=()=>this.setView("live");
      this.el("live-start").onclick=()=>this.startLive();
      this.el("live-stop").onclick=()=>this.stopLive();
      ["paths-tab","origins-tab","live-tab"].forEach(id=>this.el(id).onkeydown=(event)=>{
        if (["ArrowLeft","ArrowRight"].includes(event.key)) {event.preventDefault();const views=["paths","origins","live"],index=views.indexOf(this.view),direction=event.key==="ArrowRight"?1:-1;this.setView(views[(index+direction+views.length)%views.length]);this.el(`${this.view}-tab`).focus();}
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
      this.live={events:[],socket:null};
      this.setView("paths");
      this.el("resources").value="AS3333";
    }
    disconnectedCallback() { clearInterval(this.requestTimer); clearInterval(this.accessTimer); clearTimeout(this.timer); this.controller?.abort(); this.stopLive(); }
    savedTheme() {
      try { return localStorage.getItem("bgp-routing-exposure-theme")||"soc"; }
      catch { return "soc"; }
    }
    applyTheme(theme) {
      const allowed=new Set(["soc","nord","contrast","matrix","mucaro","notebook","amber"]);
      const selected=allowed.has(theme)?theme:"soc";
      this.setAttribute("data-theme",selected);
      document.documentElement.dataset.bgpTheme=selected;
      this.el("theme").value=selected;
      try { localStorage.setItem("bgp-routing-exposure-theme",selected); } catch {}
    }
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
      if(this.view==="live"&&view!=="live")this.stopLive();
      this.view=view;
      const paths=view==="paths", live=view==="live";
      this.root.querySelector("form").hidden=live;
      this.el("investigation-tools").hidden=!paths;
      this.el("investigation-results").hidden=true;
      this.investigation=null;this.bundleBlob=null;this.job=null;this.payload=null;
      ["paths","origins","live"].forEach(name=>{this.el(`${name}-tab`).setAttribute("aria-selected",String(name===view));this.el(`${name}-tab`).tabIndex=name===view?0:-1;});
      this.el("results").hidden=true;this.el("path-results").hidden=true;this.el("live-view").hidden=!live;this.el("empty").hidden=live;
      ["request-count","request-notice","notice","batch-progress","result-completeness","cancel-job","status"].forEach(id=>this.el(id).hidden=live);
      if(live)return;
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
    liveStatus(message, error=false, busy=false) {
      const element=this.el("live-status");
      element.textContent=message;
      element.className=`status${error?" error":""}${busy?" busy":""}`;
    }
    liveAsn() {
      const value=this.el("live-asn").value.trim().replace(/^AS/i,"");
      if(!/^\d{1,10}$/.test(value))return null;
      const asn=Number(value);
      return Number.isSafeInteger(asn)&&asn>0&&asn<=4294967295?asn:null;
    }
    renderLiveEvents() {
      const container=this.el("live-events");container.replaceChildren();
      const events=this.live?.events||[];
      const node=(tag,text,cls)=>{const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(cls)element.className=cls;return element;};
      if(!events.length) {container.append(node("p","No live events yet.","muted"));return;}
      const list=node("ol",undefined,"live-event-list");container.append(list);
      for(const event of events) {
        const item=node("li",undefined,"live-event");list.append(item);
        item.append(node("strong",event.kind));
        item.append(node("span",`${event.observedAt} · ${event.collector} · peer AS${event.peerAsn}`,"small muted"));
        if(event.prefixes) item.append(node("span",event.prefixes,"live-prefixes"));
        if(event.path) item.append(node("span",event.path,"live-path"));
      }
    }
    liveEvent(message) {
      if(message?.type==="ris_error") {
        const detail=message.data?.message||message.data?.error||"RIS Live rejected the subscription.";
        this.liveStatus(`RIS Live error: ${detail}`,true);return;
      }
      if(message?.type!=="ris_message"||!message.data)return;
      const data=message.data;
      if(data.type&&data.type!=="UPDATE")return;
      const prefixes=(entries)=>entries.flatMap(entry=>Array.isArray(entry?.prefixes)?entry.prefixes:[]).filter(value=>typeof value==="string");
      const announced=prefixes(data.announcements||[]),withdrawn=prefixes(data.withdrawals||[]);
      if(!announced.length&&!withdrawn.length)return;
      const label=announced.length&&withdrawn.length?"Announcement and withdrawal":announced.length?"Announcement":"Withdrawal";
      const prefixText=[announced.length?`Announced: ${announced.slice(0,8).join(", ")}${announced.length>8?` +${announced.length-8} more`:""}`:"",withdrawn.length?`Withdrawn: ${withdrawn.slice(0,8).join(", ")}${withdrawn.length>8?` +${withdrawn.length-8} more`:""}`:""].filter(Boolean).join(" · ");
      const time=typeof data.timestamp==="number"?new Date(data.timestamp*1000):new Date();
      const event={kind:label,observedAt:time.toISOString().replace("T"," ").replace(".000Z"," UTC"),collector:data.host||"RIS collector unavailable",peerAsn:data.peer_asn||"?",prefixes:prefixText,path:Array.isArray(data.path)&&data.path.length?data.path.map(asn=>`AS${asn}`).join(" → "):""};
      if(!this.live)return;
      this.live.events.unshift(event);this.live.events.length=Math.min(this.live.events.length,250);
      this.renderLiveEvents();
    }
    startLive() {
      const asn=this.liveAsn();
      if(!asn)return this.liveStatus("Enter a valid AS number from 1 through 4,294,967,295.",true);
      this.stopLive(false);
      const role=this.el("live-role").value;
      const stream={events:[],socket:null,asn,role,stopped:false};this.live=stream;this.renderLiveEvents();
      this.el("live-start").disabled=true;this.el("live-stop").hidden=false;
      this.liveStatus(`Connecting to RIPE RIS for AS${asn}.`,false,true);
      let socket;
      try {socket=new WebSocket("wss://ris-live.ripe.net/v1/ws/?client=bgp-routing-exposure-lookup");}
      catch {this.liveStatus("This browser could not open a RIS Live connection.",true);this.el("live-start").disabled=false;this.el("live-stop").hidden=true;return;}
      stream.socket=socket;
      socket.onopen=()=>{
        if(this.live!==stream||stream.stopped)return;
        socket.send(JSON.stringify({type:"ris_subscribe",data:{type:"UPDATE",path:role==="origin"?`${asn}$`:String(asn),socketOptions:{includeRaw:false}}}));
        this.liveStatus(`Watching AS${asn} ${role==="origin"?"as an origin":"anywhere in observed paths"}.`);
      };
      socket.onmessage=event=>{try {if(this.live===stream&&!stream.stopped)this.liveEvent(JSON.parse(event.data));} catch {this.liveStatus("RIS Live sent an unreadable event.",true);}};
      socket.onerror=()=>{if(this.live===stream&&!stream.stopped)this.liveStatus("RIS Live connection error. Check network or proxy access.",true);};
      socket.onclose=()=>{
        if(this.live!==stream)return;
        stream.socket=null;this.el("live-start").disabled=false;this.el("live-stop").hidden=true;
        if(!stream.stopped)this.liveStatus("RIS Live connection closed. Start again to reconnect.",true);
      };
    }
    stopLive(clear=true) {
      const stream=this.live;
      if(!stream)return;
      stream.stopped=true;
      if(stream.socket&&stream.socket.readyState<2)stream.socket.close(1000,"Stopped by analyst");
      stream.socket=null;this.el?.("live-start")&&(this.el("live-start").disabled=false);this.el?.("live-stop")&&(this.el("live-stop").hidden=true);
      if(clear) {stream.events=[];this.renderLiveEvents();this.liveStatus("Live view stopped. Displayed events were cleared.");}
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
        (truncated?"Displayed path evidence is limited; counts include all accepted RIS routes, while the displayed list and CSV retain a bounded subset. Narrow the target to investigate further. ":"")+
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
      ["resolve","import","example","resources","date","paths-tab","origins-tab","live-tab","capture","compare-dates","compare-before","compare-after","open-investigation","replay-investigation","bundle-export","comparison-export","snapshot-select"].forEach(id=>this.el(id).disabled=busy);
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
    visibilityContext(group) {
      if (group.visibility) return group.visibility;
      const collectorCount=group.collectors?.length||0;
      const label=collectorCount<=1?"Limited public routing visibility":collectorCount<=3?"Multi-collector public routing visibility":"Broader public routing visibility";
      return {label,collectorCount,peerCount:group.peerCount||0,prefixCount:group.prefixes?.length||0};
    }
    countryName(code) {
      try { return new Intl.DisplayNames(["en"],{type:"region"}).of(code)||code; }
      catch { return code; }
    }
    groupCountryContext(group, organizations) {
      const asns=[...group.neighbors.map(neighbor=>neighbor.asn),group.origin];
      const pathRecordsByAs=new Map();
      const originRecords=[];
      for(const neighbor of group.neighbors) {
        const records=neighbor.paths.map(path=>({...path,adjacent:neighbor.asn,origin:group.origin}));
        pathRecordsByAs.set(neighbor.asn,records);
        originRecords.push(...records);
      }
      pathRecordsByAs.set(group.origin,originRecords);
      return this.countryContext(asns,organizations,group.origin,{
        open:true,
        group:true,
        mapFirst:true,
        pathRecordsByAs,
        organizationNames:organizations,
        roles:asns.map((asn,index)=>index===asns.length-1?"Origin AS":"Observed adjacent AS"),
        note:"Country markers reflect CAIDA's registered organization-country field. They place each marker center inside the bundled country boundary; they do not depict a geographic route, network presence, or collector location."
      });
    }
    countryContext(asns, organizations, origin, options={}) {
      const details=document.createElement("details");details.className="country-context";
      if(options.group)details.classList.add("group-country-context");
      const summary=document.createElement("summary");summary.textContent="Registered organization country context";summary.hidden=Boolean(options.mapFirst);details.append(summary);
      const note=document.createElement("p");note.className="small muted";note.textContent=options.note||"Country markers reflect CAIDA's registered organization-country field. The leftmost AS is part of a route advertisement observed by RIS; it is not a traffic source or a direct relationship with the origin.";
      if(!options.mapFirst)details.append(note);
      const list=document.createElement("ol");list.className="country-hop-list";
      const hops=asns.map((asn,index)=>{
        const info=organizations[String(asn)]||{};
        const country=(info.country||"").toUpperCase();
        const role=options.roles?.[index]|| (index===asns.length-1?"Origin":index===asns.length-2?"Adjacent to origin":index===0?"Leftmost AS in RIS-observed path":"Observed AS_PATH hop");
        const hop={asn,country,role,organization:info.name||info.asName||"Organization unavailable",asName:info.asName||"",pathRecords:options.pathRecordsByAs?.get(asn)||[],organizationNames:options.organizationNames||organizations,countryAggregate:Boolean(options.group)};
        const item=document.createElement("li");
        const marker=document.createElement("span");marker.className="country-hop-marker";marker.textContent="–";item.append(marker);
        const content=document.createElement("span");content.className="country-hop-content";
        const heading=document.createElement("strong");heading.textContent=role;if(index===0)heading.title="The leftmost ASN in a route advertisement observed by a RIS collector. It is not a traffic source or a direct relationship with the origin.";content.append(heading);
        const identity=document.createElement("span");identity.textContent=`AS${asn} · ${hop.organization}${hop.asName&&hop.asName!==hop.organization?` · ${hop.asName}`:""}`;content.append(identity);
        const location=document.createElement("span");location.className="muted";location.textContent=country?`${this.countryName(country)} (${country})`:"Country unavailable";content.append(location);
        item.append(content);list.append(item);hop.marker=marker;
        return hop;
      });
      const stage=document.createElement("div");stage.className="country-map-stage";
      if(options.mapFirst) {
        const more=document.createElement("details");more.className="country-map-details";
        const moreSummary=document.createElement("summary");moreSummary.textContent=`Show country context details (${asns.length} ASes)`;more.append(moreSummary,note,list);
        details.append(stage,more);
      } else {
        details.append(list,stage);
      }
      let rendered=false;
      details.addEventListener("toggle",()=>{if(details.open&&!rendered){rendered=true;this.renderCountryMap(stage,hops);}});
      if(options.open){details.open=true;rendered=true;this.renderCountryMap(stage,hops);}
      return details;
    }
    async countryGeometry() {
      if(!this.countryGeometryPromise) {
        this.countryGeometryPromise=fetch(new URL("world-countries.json",assets),{cache:"force-cache"}).then(response=>{
          if(!response.ok)throw new Error("Country map unavailable");
          return response.json();
        }).then(data=>{
          if(data?.type!=="FeatureCollection"||!Array.isArray(data.features))throw new Error("Invalid country map");
          return data;
        }).catch(error=>{this.countryGeometryPromise=null;throw error;});
      }
      return this.countryGeometryPromise;
    }
    countryPath(geometry) {
      const polygons=geometry?.type==="Polygon"?[geometry.coordinates]:geometry?.type==="MultiPolygon"?geometry.coordinates:[];
      const project=([longitude,latitude])=>`${((Number(longitude)+180)*2).toFixed(1)},${(180-Number(latitude)*2).toFixed(1)}`;
      return polygons.flatMap(polygon=>(polygon||[]).map(ring=>Array.isArray(ring)&&ring.length?`M${ring.map(project).join("L")}Z`:"")).join("");
    }
    pointInRing(point,ring) {
      let inside=false;
      for(let index=0,previous=ring.length-1;index<ring.length;previous=index++) {
        const [x,y]=ring[index],[previousX,previousY]=ring[previous];
        if((y>point[1])!==(previousY>point[1])&&point[0]<(previousX-x)*(point[1]-y)/(previousY-y)+x)inside=!inside;
      }
      return inside;
    }
    ringCentroid(ring) {
      let area=0,x=0,y=0;
      for(let index=0,previous=ring.length-1;index<ring.length;previous=index++) {
        const [x1,y1]=ring[previous],[x2,y2]=ring[index],cross=x1*y2-x2*y1;
        area+=cross;x+=(x1+x2)*cross;y+=(y1+y2)*cross;
      }
      return Math.abs(area)>0.00001?[x/(3*area),y/(3*area)]:null;
    }
    interiorPoint(polygon) {
      const [outer,...holes]=polygon,inside=point=>this.pointInRing(point,outer)&&!holes.some(ring=>this.pointInRing(point,ring));
      const centroid=this.ringCentroid(outer);
      if(centroid&&inside(centroid))return centroid;
      const longitudes=outer.map(point=>point[0]),latitudes=outer.map(point=>point[1]);
      const minLongitude=Math.min(...longitudes),maxLongitude=Math.max(...longitudes),minLatitude=Math.min(...latitudes),maxLatitude=Math.max(...latitudes);
      for(const divisions of [9,17,31]) {
        const candidates=[];
        for(let row=0;row<divisions;row++)for(let column=0;column<divisions;column++) {
          const point=[minLongitude+(column+.5)*(maxLongitude-minLongitude)/divisions,minLatitude+(row+.5)*(maxLatitude-minLatitude)/divisions];
          candidates.push(point);
        }
        candidates.sort((left,right)=>((left[0]-(centroid?.[0]??0))**2+(left[1]-(centroid?.[1]??0))**2)-((right[0]-(centroid?.[0]??0))**2+(right[1]-(centroid?.[1]??0))**2));
        const point=candidates.find(inside);if(point)return point;
      }
      return null;
    }
    countryPoint(feature) {
      return this.countryPoints(feature,1)[0]||null;
    }
    countryPoints(feature,count) {
      const polygons=feature.geometry?.type==="Polygon"?[feature.geometry.coordinates]:feature.geometry?.type==="MultiPolygon"?feature.geometry.coordinates:[];
      const area=ring=>Math.abs(ring.reduce((total,point,index)=>{const next=ring[(index+1)%ring.length];return total+point[0]*next[1]-next[0]*point[1];},0));
      const polygon=[...polygons].filter(polygon=>polygon?.[0]?.length).sort((left,right)=>area(right[0])-area(left[0]))[0];
      if(!polygon)return [];
      const [outer,...holes]=polygon,inside=point=>this.pointInRing(point,outer)&&!holes.some(ring=>this.pointInRing(point,ring));
      const centroid=this.ringCentroid(outer),candidates=[];
      if(centroid&&inside(centroid))candidates.push(centroid);
      const longitudes=outer.map(point=>point[0]),latitudes=outer.map(point=>point[1]);
      const minLongitude=Math.min(...longitudes),maxLongitude=Math.max(...longitudes),minLatitude=Math.min(...latitudes),maxLatitude=Math.max(...latitudes);
      for(const divisions of [13,23,37]) for(let row=0;row<divisions;row++)for(let column=0;column<divisions;column++) {
        const point=[minLongitude+(column+.5)*(maxLongitude-minLongitude)/divisions,minLatitude+(row+.5)*(maxLatitude-minLatitude)/divisions];
        if(inside(point))candidates.push(point);
      }
      const selected=[];
      while(selected.length<count&&candidates.length) {
        let bestIndex=0,bestScore=-1;
        candidates.forEach((candidate,index)=>{
          const score=selected.length?Math.min(...selected.map(point=>(candidate[0]-point[0])**2+(candidate[1]-point[1])**2)):-((candidate[0]-(centroid?.[0]??candidate[0]))**2+(candidate[1]-(centroid?.[1]??candidate[1]))**2);
          if(score>bestScore){bestScore=score;bestIndex=index;}
        });
        selected.push(candidates.splice(bestIndex,1)[0]);
      }
      return selected.map(point=>({x:(point[0]+180)*2,y:180-point[1]*2}));
    }
    async renderCountryMap(stage,hops) {
      stage.replaceChildren();
      const loading=document.createElement("p");loading.className="small muted";loading.textContent="Loading local country map…";stage.append(loading);
      if(!hops.some(hop=>hop.country)) { loading.textContent="No registered organization country was available for this path.";return; }
      try {
        const data=await this.countryGeometry();
        const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");svg.classList.add("country-map");svg.setAttribute("viewBox","0 0 720 360");svg.setAttribute("role","img");svg.setAttribute("aria-label","Registered organization country context. Double-click an empty map area to zoom.");
        const title=document.createElementNS("http://www.w3.org/2000/svg","title");title.textContent="Registered organization country context";svg.append(title);
        const viewport={x:0,y:0,width:720,height:360};let zoomLevel=0;
        const updateViewport=()=>svg.setAttribute("viewBox",`${viewport.x.toFixed(2)} ${viewport.y.toFixed(2)} ${viewport.width.toFixed(2)} ${viewport.height.toFixed(2)}`);
        const resetViewport=()=>{viewport.x=0;viewport.y=0;viewport.width=720;viewport.height=360;zoomLevel=0;updateViewport();};
        const zoomAt=(x,y)=>{const nextWidth=viewport.width/2,nextHeight=viewport.height/2;viewport.x=Math.max(0,Math.min(720-nextWidth,x-(x-viewport.x)*nextWidth/viewport.width));viewport.y=Math.max(0,Math.min(360-nextHeight,y-(y-viewport.y)*nextHeight/viewport.height));viewport.width=nextWidth;viewport.height=nextHeight;zoomLevel++;updateViewport();};
        svg.addEventListener("dblclick",event=>{if(event.target.closest?.(".country-map-marker"))return;const rect=svg.getBoundingClientRect();if(zoomLevel>=2)resetViewport();else zoomAt(viewport.x+(event.clientX-rect.left)*viewport.width/rect.width,viewport.y+(event.clientY-rect.top)*viewport.height/rect.height);event.preventDefault();});
        const features=new Map(),shapes=new Map();
        for(const feature of data.features) {
          const code=(feature.properties?.ISO_A2_EH||feature.properties?.ISO_A2||"").toUpperCase();
          const path=this.countryPath(feature.geometry);if(!path)continue;
          const shape=document.createElementNS("http://www.w3.org/2000/svg","path");shape.classList.add("country-shape");shape.setAttribute("d",path);svg.append(shape);
          if(code&&code!=="-99") {
            if(!features.has(code))features.set(code,[]);features.get(code).push(feature);
            if(!shapes.has(code))shapes.set(code,[]);shapes.get(code).push(shape);
          }
        }
        const eligible=hops.filter(hop=>hop.country&&features.has(hop.country));
        const origins=eligible.filter(hop=>hop.role==="Origin AS"||hop.role==="Origin");
        const adjacentHops=eligible.filter(hop=>hop.role!=="Origin AS"&&hop.role!=="Origin");
        const aggregateByCountry=Boolean(adjacentHops[0]?.countryAggregate);
        let mapEntries=[];
        if(aggregateByCountry) {
          const grouped=new Map();
          adjacentHops.forEach(hop=>{if(!grouped.has(hop.country))grouped.set(hop.country,[]);grouped.get(hop.country).push(hop);});
          mapEntries=[...grouped.entries()].sort((left,right)=>right[1].length-left[1].length||left[0].localeCompare(right[0])).map(([country,members])=>({country,role:"Observed adjacent ASes",members:members.sort((left,right)=>Number(left.asn)-Number(right.asn)),organizationNames:members[0].organizationNames}));
          mapEntries.push(...origins);
        } else {
          mapEntries=[...adjacentHops.slice(0,Math.max(0,12-origins.length)),...origins].slice(0,12);
        }
        const byCountry=new Map();
        mapEntries.forEach(entry=>{if(!byCountry.has(entry.country))byCountry.set(entry.country,[]);byCountry.get(entry.country).push(entry);});
        const markers=[];
        for(const [country,entries] of byCountry) {
          const feature=[...features.get(country)].sort((left,right)=>JSON.stringify(right.geometry).length-JSON.stringify(left.geometry).length)[0];
          this.countryPoints(feature,entries.length).forEach((point,index)=>markers.push({entry:entries[index],point}));
        }
        markers.forEach(({entry,point},index)=>{
          const number=entry.members?String(entry.members.length):String(index+1);
          shapes.get(entry.country)?.forEach(shape=>shape.classList.add("country-shape-active"));
          const isOrigin=entry.role==="Origin"||entry.role==="Origin AS";
          const group=document.createElementNS("http://www.w3.org/2000/svg","g");group.classList.add("country-map-marker",isOrigin?"country-map-origin":"country-map-adjacent");
          const markerTitle=document.createElementNS("http://www.w3.org/2000/svg","title");markerTitle.textContent=entry.members?`${entry.members.length} observed adjacent ASes registered in ${this.countryName(entry.country)} (${entry.country})`:`${number}. ${entry.role}: AS${entry.asn}, ${entry.organization}, ${entry.country}`;group.append(markerTitle);
          const circle=document.createElementNS("http://www.w3.org/2000/svg","circle");circle.setAttribute("cx",String(point.x));circle.setAttribute("cy",String(point.y));circle.setAttribute("r",String(entry.members?Math.max(7,4+number.length*2):7));circle.style.fill=isOrigin?"#ffe5a0":"#d5f7ec";group.append(circle);
          const label=document.createElementNS("http://www.w3.org/2000/svg","text");label.setAttribute("x",String(point.x));label.setAttribute("y",String(point.y+.5));label.style.fill="#101718";label.style.fontSize=entry.members&&number.length>2?"8px":"10px";label.textContent=number;group.append(label);
          group.setAttribute("role","button");group.setAttribute("tabindex","0");group.setAttribute("aria-label",entry.members?`Inspect ${entry.members.length} observed adjacent ASes in ${this.countryName(entry.country)}`:`Inspect ${entry.role}, AS${entry.asn}`);
          const select=()=>this.showCountryPopup(svg,group,entry);
          group.addEventListener("click",select);group.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" "){event.preventDefault();select();}});
          svg.append(group);
          if(!aggregateByCountry&&entry.marker)entry.marker.textContent=number;
        });
        stage.replaceChildren(svg);
        const caption=document.createElement("p");caption.className="small muted";caption.textContent=aggregateByCountry?`${mapEntries.filter(entry=>entry.members).length} registered countries cover ${adjacentHops.length} observed adjacent ASes. The origin AS is shown separately when it has a registered country. Country counts do not depict a geographic route, network presence, or collector location. Double-click an empty map area to zoom; a third double-click resets the view.`:`${markers.length} of ${hops.filter(hop=>hop.country).length} ASes with a registered country are shown${eligible.length>mapEntries.length?" (first 12 to keep the map readable)":""}. Each marker center is generated inside its displayed country boundary. Double-click an empty map area to zoom; a third double-click resets the view.`;stage.append(caption);
      } catch {
        loading.textContent="The local country map could not be loaded. The organization-country list remains available above.";
      }
    }
    showCountryPopup(svg,marker,hop) {
      const node=(tag,text,cls)=>{const element=document.createElement(tag);if(text!==undefined)element.textContent=text;if(cls)element.className=cls;return element;};
      svg.querySelectorAll(".country-map-marker.selected").forEach(item=>item.classList.remove("selected"));
      marker.classList.add("selected");
      this.root.querySelector(".country-map-popup")?.close();
      this.root.querySelector(".country-map-popup")?.remove();
      const dialog=document.createElement("dialog");dialog.className="country-map-popup";
      const header=document.createElement("div");header.className="country-map-popup-header";
      const close=document.createElement("button");close.type="button";close.textContent="Close";close.addEventListener("click",()=>dialog.close());
      if(hop.members) {
        const title=document.createElement("div");title.append(node("strong",`${hop.members.length} observed adjacent ASes`),node("span",`${this.countryName(hop.country)} (${hop.country})`,"muted"));header.append(title,close);dialog.append(header);
        const introduction=document.createElement("p");introduction.className="small muted";introduction.textContent="Each listed AS was observed immediately before the origin AS in at least one returned RIS route. This is registered organization-country context, not a geographic route or network presence.";dialog.append(introduction);
        const members=document.createElement("ol");members.className="country-map-popup-as-list";
        hop.members.forEach(member=>{const item=document.createElement("li");const name=member.organization||member.asName||"Organization unavailable";item.textContent=`AS${member.asn} · ${name}${member.asName&&member.asName!==name?` · ${member.asName}`:""}`;members.append(item);});
        dialog.append(members);dialog.addEventListener("close",()=>{marker.classList.remove("selected");dialog.remove();});this.root.append(dialog);dialog.showModal();return;
      }
      const title=document.createElement("div");title.append(node("strong",`${hop.role}: AS${hop.asn}`),node("span",`${hop.organization}${hop.asName&&hop.asName!==hop.organization?` · ${hop.asName}`:""} · ${hop.country?`${this.countryName(hop.country)} (${hop.country})`:"Country unavailable"}`,"muted"));
      header.append(title,close);dialog.append(header);
      const introduction=document.createElement("p");introduction.className="small muted";introduction.textContent=hop.pathRecords.length?`Observed path evidence containing this ${hop.role.toLowerCase()}. The adjacent AS and origin are highlighted.`:"No returned path evidence is available for this AS.";dialog.append(introduction);
      const records=document.createElement("div");records.className="country-map-popup-paths";
      for(const path of hop.pathRecords) {
        const record=document.createElement("div");record.className="path-record";
        record.append(node("div",`${path.prefix} · ${path.peerCount} collector peers · ${path.collectors.join(", ")}`,"small muted"));
        const chain=document.createElement("div");chain.className="as-path";
        path.asns.forEach((asn,index)=>{
          if(index)chain.append(node("span","→","muted"));
          const info=hop.organizationNames[String(asn)]||{};
          const names=[...new Set([info.asName,info.name].filter(Boolean))];
          const label=names.length?names.join(" · "):"Name unavailable";
          const country=info.country?`, ${info.country}`:"";
          const classes=["as-hop"];
          if(asn===path.adjacent)classes.push("map-path-adjacent");
          if(asn===path.origin)classes.push("map-path-origin");
          if(asn===hop.asn)classes.push("map-path-selected");
          chain.append(node("span",`AS${asn} — ${label}${country}`,classes.join(" ")));
        });
        record.append(chain);records.append(record);
      }
      dialog.append(records);dialog.addEventListener("close",()=>{marker.classList.remove("selected");dialog.remove();});this.root.append(dialog);dialog.showModal();
    }
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
          section.append(this.groupCountryContext(group,result.asns));
          const visibility=this.visibilityContext(group);
          const observedAt=result.observation?.observedAt?` · observed ${result.observation.observedAt.replace("T"," ").replace("+00:00"," UTC")}`:"";
          section.append(node("p",`${visibility.label} · ${visibility.collectorCount} RIS collectors · ${visibility.peerCount} distinct collector peers · ${visibility.prefixCount} observed prefixes · ${group.neighbors.length} observed adjacent ASes${observedAt}`,"small muted"));
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
            if(neighbor.pathsTruncated)cell.append(node("p",`Showing ${neighbor.paths.length} of ${neighbor.pathCount} observed path/prefix combinations.`,"warning"));
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
