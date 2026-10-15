package service

import (
    "context"
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
