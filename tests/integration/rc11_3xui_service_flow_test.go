package service

import (
    "context"
    "encoding/json"
    "sync"
    "testing"

    "github.com/mhsanaei/3x-ui/v3/internal/database"
    "github.com/mhsanaei/3x-ui/v3/internal/database/model"
    "github.com/mhsanaei/3x-ui/v3/internal/web/runtime"
)

// Captures the exact Client payload the REAL v3.10.0 service sends to a Node.
// No production network, Node credentials, or fake implementation of BulkAdjust.
type rc11FlowRecorder struct {
    fakeNodeRuntime
    mu sync.Mutex
    byTag map[string]string
}
func (f *rc11FlowRecorder) UpdateUser(ctx context.Context, ib *model.Inbound, oldEmail string, c model.Client) error {
    f.mu.Lock()
    f.byTag[ib.Tag] = c.Flow
    f.mu.Unlock()
    return f.fakeNodeRuntime.UpdateUser(ctx, ib, oldEmail, c)
}
func (f *rc11FlowRecorder) flow(tag string) string {
    f.mu.Lock()
    defer f.mu.Unlock()
    return f.byTag[tag]
}

// Executed against the pinned, real upstream 3x-ui Go service + SQLite,
// not a Python reimplementation. Flow transport to a Node is intercepted.
func TestRC11RealityFlowNoopBulkAdjustOnUpstreamService(t *testing.T) {
    setupBulkDB(t)
    startSerializedWriter(t)
    nodeID, _ := setupNodeRuntime(t)
    probe := &rc11FlowRecorder{byTag: make(map[string]string)}
    runtime.GetManager().SetRuntimeOverride(nodeID, probe)

    const vision = "xtls-rprx-vision"
    const email = "rc11-reassignment@example.com"
    client := model.Client{
        Email: email, ID: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        SubID: "rc11-test-sub", Flow: vision, Enable: true,
        ExpiryTime: 2000000000000,
    }
    db := database.GetDB()
    reality := &model.Inbound{
        UserId: 1, NodeID: &nodeID, Tag: "rc11-reality", Enable: true,
        Port: 47821, Protocol: model.VLESS,
        StreamSettings: `{"network":"tcp","security":"reality"}`,
        Settings: clientsSettings(t, []model.Client{client}),
    }
    other := &model.Inbound{
        UserId: 1, NodeID: &nodeID, Tag: "rc11-ws", Enable: true,
        Port: 47822, Protocol: model.VLESS,
        StreamSettings: `{"network":"ws","security":"none"}`,
        Settings: clientsSettings(t, []model.Client{clientWithInboundFlow(client, &model.Inbound{Protocol: model.VLESS, StreamSettings: `{"network":"ws","security":"none"}`})}),
    }
    if err := db.Create(reality).Error; err != nil { t.Fatal(err) }
    if err := db.Create(other).Error; err != nil { t.Fatal(err) }

    svc := &ClientService{}
    inboundSvc := &InboundService{}
    // Mirror the multi-inbound ordering already tested by upstream #4792:
    // Reality -> non-Flow WS causes shared clients.flow to become blank.
    if err := svc.SyncInbound(nil, reality.Id, []model.Client{client}); err != nil { t.Fatal(err) }
    nonflow := clientWithInboundFlow(client, other)
    if err := svc.SyncInbound(nil, other.Id, []model.Client{nonflow}); err != nil { t.Fatal(err) }
    rec, err := svc.GetRecordByEmail(nil, email)
    if err != nil { t.Fatal(err) }
    masterEffective, err := svc.EffectiveFlow(nil, rec.Id)
    if err != nil { t.Fatal(err) }
    if masterEffective != vision {
        t.Fatalf("Master EffectiveFlow=%q want=%q", masterEffective, vision)
    }
    if rec.Flow != "" {
        t.Fatalf("Shared clients.flow=%q, require empty to cover realistic #4792 case", rec.Flow)
    }
    t.Logf("AFTER_REASSIGN_METADATA: Master EffectiveFlow=%q, shared clients.flow=%q", masterEffective, rec.Flow)

    // This is the REAL upstream clients/update operation from the bot's
    // Plan + Reconcile; the tariff clear/reassign buttons only change bot DB.
    updated := *rec.ToClient()
    updated.Flow = vision
    updated.TotalGB = 100 * 1024 * 1024 * 1024
    updated.ExpiryTime = 2200000000000
    updated.LimitIP = 2
    if _, err := svc.Update(inboundSvc, rec.Id, updated, 0); err != nil {
        t.Fatalf("Update full client failed: %v", err)
    }
    t.Logf("AFTER_UPDATE: Node Reality payload.flow=%q", probe.flow(reality.Tag))
    if got := probe.flow(reality.Tag); got != vision {
        t.Fatalf("Update itself sent wrong Reality Flow=%q", got)
    }

    // Multi-inbound SyncInbound may complete in either order during Update.
    // Recreate deterministically the upstream #4792 state: a non-Flow inbound
    // synchronized last, so shared clients.flow is blank while the Reality
    // per-inbound override remains Vision. This is a disposable SQLite row.
    if err := db.Model(&model.ClientRecord{}).Where("email = ?", email).
        Update("flow", "").Error; err != nil {
        t.Fatalf("seed stale shared flow after Update: %v", err)
    }
    check, err := svc.GetRecordByEmail(nil, email)
    if err != nil { t.Fatal(err) }
    if check.Flow != "" { t.Fatalf("stale shared flow not seeded: %q", check.Flow) }
    beforeBulk, err := svc.EffectiveFlow(nil, check.Id)
    if err != nil || beforeBulk != vision {
        t.Fatalf("Reality override must remain Vision: flow=%q err=%v", beforeBulk, err)
    }

    // Current rc.10 bot ALWAYS calls this even if Master reports Vision.
    if _, _, err := svc.BulkAdjust(inboundSvc, []string{email}, 0, 0, vision, nil, ""); err != nil {
        t.Fatalf("BulkAdjust failed: %v", err)
    }
    afterBulk := probe.flow(reality.Tag)
    effective, err := svc.EffectiveFlow(nil, rec.Id)
    if err != nil { t.Fatal(err) }
    t.Logf("AFTER_BULK: Master EffectiveFlow=%q Node Reality payload.flow=%q", effective, afterBulk)
    if effective != vision { t.Fatalf("Master Flow no longer Vision: %q", effective) }
    if afterBulk != "" {
        t.Fatalf("Expected v3.10.0 no-op BulkAdjust to send empty Flow, got %q (upstream may be fixed)", afterBulk)
    }
    t.Log("RC11_ROOT_PATH_CONFIRMED: no-op bulkAdjust pushes empty shared clients.flow to Reality Node")
}


func TestRC11ScopedFlowEditDoesNotTouchAnotherInbound(t *testing.T) {
    setupBulkDB(t)
    startSerializedWriter(t)
    nodeID, _ := setupNodeRuntime(t)
    probe := &rc11FlowRecorder{byTag: make(map[string]string)}
    runtime.GetManager().SetRuntimeOverride(nodeID, probe)

    const email = "scoped-flow@example.com"
    const originalFlow = "xtls-rprx-vision"
    client := model.Client{
        Email: email, ID: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        SubID: "scoped-flow-sub", Flow: originalFlow, Enable: true,
        ExpiryTime: 2000000000000, TotalGB: 107374182400, LimitIP: 10,
    }
    db := database.GetDB()
    mk := func(tag string, port int) *model.Inbound {
        return &model.Inbound{
            UserId: 1, NodeID: &nodeID, Tag: tag, Enable: true,
            Port: port, Protocol: model.VLESS,
            StreamSettings: `{"network":"tcp","security":"reality"}`,
            Settings: clientsSettings(t, []model.Client{client}),
        }
    }
    chosen, other := mk("rc11-scoped-chosen", 47831), mk("rc11-scoped-other", 47832)
    if err := db.Create(chosen).Error; err != nil { t.Fatal(err) }
    if err := db.Create(other).Error; err != nil { t.Fatal(err) }
    svc := &ClientService{}
    inboundSvc := &InboundService{}
    if err := svc.SyncInbound(nil, chosen.Id, []model.Client{client}); err != nil { t.Fatal(err) }
    if err := svc.SyncInbound(nil, other.Id, []model.Client{client}); err != nil { t.Fatal(err) }

    before, err := svc.GetRecordByEmail(nil, email)
    if err != nil { t.Fatal(err) }
    updated := *before.ToClient()
    updated.Flow = ""
    updated.TotalGB = 107374182400
    updated.ExpiryTime = 2000000000000
    updated.LimitIP = 10
    if _, err := svc.Update(inboundSvc, before.Id, updated, 0, chosen.Id); err != nil {
        t.Fatalf("single inbound scoped Update: %v", err)
    }
    checkInbound := func(ib *model.Inbound, want string) {
        t.Helper()
        raw, err := inboundSvc.GetInbound(ib.Id)
        if err != nil { t.Fatal(err) }
        var settings struct { Clients []model.Client `json:"clients"` }
        if err := json.Unmarshal([]byte(raw.Settings), &settings); err != nil { t.Fatal(err) }
        current := settings.Clients
        if len(current) != 1 || current[0].Email != email || current[0].Flow != want {
            t.Fatalf("inbound %d (%s) Flow=%v; want %q", ib.Id, ib.Tag, current, want)
        }
    }
    checkInbound(chosen, "")
    checkInbound(other, originalFlow)
    if got := probe.flow(other.Tag); got != "" {
        // The recorder starts empty and captures only pushes after the
        // filtered Update. A nonempty value implies an unwanted push.
        t.Fatalf("unselected inbound received an unexpected Node update: %q", got)
    }
    t.Logf("SCOPED_FLOW_FILTER_PASS chosen=%d flow=none other=%d flow=%s", chosen.Id, other.Id, originalFlow)
}


// This test exercises the actual upstream Go ClientService with two different
// Node identities and mixed VLESS/AmneziaWG/Hysteria/XHTTP attachments. A
// chosen VLESS update must not write ANY other inbound or peer credential.
// All fixtures use temporary SQLite; no network panel is contacted.
func TestRC11MultiProtocolScopedFlowPreservesTunnelRecord(t *testing.T) {
    setupBulkDB(t)
    startSerializedWriter(t)
    nodeA, _ := setupNodeRuntime(t)
    db := database.GetDB()
    second := &model.Node{Name:"rc11-multiprotocol-node-two", Address:"127.0.0.1", Port:2097, ApiToken:"fixture-token", Enable:true, Status:"online"}
    if err:=db.Create(second).Error; err!=nil {t.Fatal(err)}
    nodeB:=second.Id
    recorder:=&rc11FlowRecorder{byTag:make(map[string]string)}
    runtime.GetManager().SetRuntimeOverride(nodeA,recorder)
    runtime.GetManager().SetRuntimeOverride(nodeB,recorder)
    const email="scoped-multiprotocol@example.invalid"
    const vision="xtls-rprx-vision"
    common:=model.Client{Email:email,ID:"aaaa1111-bbbb-4ccc-8ddd-eeeeeeeeeeee",SubID:"test-mp-sub",
      Enable:true,ExpiryTime:2000000000000,TotalGB:10737418240,LimitIP:2,Flow:vision}
    inboundSvc:=&InboundService{}
    svc:=&ClientService{}
    makeInbound:=func(node int,tag string,port int,proto model.Protocol,network string,withClient bool) *model.Inbound {
        clients:=[]model.Client{}
        if withClient {clients=[]model.Client{common}}
        ib:=&model.Inbound{UserId:1,NodeID:&node,Tag:tag,Port:port,Protocol:proto,Enable:true,
          StreamSettings:`{"network":"`+network+`","security":"reality"}`,Settings:clientsSettings(t,clients)}
        if err:=db.Create(ib).Error;err!=nil {t.Fatal(err)}
        return ib
    }
    chosen:=makeInbound(nodeA,"mp-vless-reality-a",46001,model.VLESS,"tcp",true)
    other:=makeInbound(nodeB,"mp-vless-reality-b",46002,model.VLESS,"tcp",true)
    if err:=svc.SyncInbound(nil,chosen.Id,[]model.Client{common});err!=nil {t.Fatal(err)}
    if err:=svc.SyncInbound(nil,other.Id,[]model.Client{common});err!=nil {t.Fatal(err)}
    record,err:=svc.GetRecordByEmail(nil,email);if err!=nil {t.Fatal(err)}
    tunnelA:=makeInbound(nodeA,"mp-awg-a",46003,model.AmneziaWG,"",false)
    tunnelB:=makeInbound(nodeB,"mp-awg-b",46004,model.AmneziaWG,"",false)
    xhttp:=makeInbound(nodeA,"mp-xhttp",46005,model.VLESS,"xhttp",false)
    hysteria:=makeInbound(nodeB,"mp-hysteria",46006,model.Hysteria,"",false)
    untouched:=[]*model.Inbound{tunnelA,tunnelB,xhttp,hysteria,other}
    for _,ib:=range untouched {
        if ib.Id==other.Id {continue} // SyncInbound already added this link.
        if err:=db.Create(&model.ClientInbound{ClientId:record.Id,InboundId:ib.Id}).Error;err!=nil {t.Fatal(err)}
    }
    // Populate the shared peer fields exactly as the upstream model stores
    // them. The chosen VLESS update must not clear even a single field.
    wgValues:=map[string]any{"wg_private_key":"fixture-private","wg_public_key":"fixture-public",
      "wg_allowed_ips":"10.9.1.5/32","wg_pre_shared_key":"fixture-psk","wg_keep_alive":25,
      "wg_forwarded_ports":"443"}
    if err:=db.Model(&model.ClientRecord{}).Where("id = ?",record.Id).Updates(wgValues).Error;err!=nil {t.Fatal(err)}
    oldSettings:=make(map[int]string)
    for _,ib:=range untouched {oldSettings[ib.Id]=ib.Settings}
    before,err:=svc.GetRecordByEmail(nil,email);if err!=nil {t.Fatal(err)}
    updated:=*before.ToClient()
    updated.Flow=""
    if _,err:=svc.Update(inboundSvc,before.Id,updated,before.LimitHwid,chosen.Id);err!=nil {
        t.Fatalf("scoped Update: %v",err)
    }
    after,err:=svc.GetRecordByEmail(nil,email);if err!=nil {t.Fatal(err)}
    if after.PrivateKey!=before.PrivateKey || after.PublicKey!=before.PublicKey ||
        after.AllowedIPs!=before.AllowedIPs || after.PreSharedKey!=before.PreSharedKey ||
        after.KeepAlive!=before.KeepAlive || after.ForwardedPorts!=before.ForwardedPorts {
        t.Fatal("scoped VLESS Flow corrupted shared WG/AWG peer fields")
    }
    for _,ib:=range untouched {
        actual,err:=inboundSvc.GetInbound(ib.Id);if err!=nil {t.Fatal(err)}
        if actual.Settings!=oldSettings[ib.Id] {t.Fatalf("other inbound changed: %d",ib.Id)}
    }
    // Only the selected node/inbound gets an outbound runtime UpdateUser.
    // A shared ClientRecord DB mutation can dirty node sync state; that does
    // not authorize a direct unselected Node mutation.
    if recorder.flow(other.Tag)!="" {t.Fatal("unselected node got Flow payload")}
    chosenAfter,err:=inboundSvc.GetInbound(chosen.Id);if err!=nil {t.Fatal(err)}
    var parsed struct{Clients []model.Client `json:"clients"`}
    if err:=json.Unmarshal([]byte(chosenAfter.Settings),&parsed);err!=nil {t.Fatal(err)}
    if len(parsed.Clients)!=1 || parsed.Clients[0].Flow!="" {t.Fatal("chosen inbound flow not cleared")}
}
