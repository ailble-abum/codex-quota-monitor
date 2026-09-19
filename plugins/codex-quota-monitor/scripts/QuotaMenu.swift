import AppKit

final class QuotaMenu: NSObject, NSApplicationDelegate {
    let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    let root = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/CodexQuotaMonitor")
    var timer: Timer?
    var snapshot: [String:Any] = [:]
    func applicationDidFinishLaunching(_ notification: Notification) {
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 10, repeats: true) { [weak self] _ in self?.refresh() }
    }
    func color(_ remaining: Double) -> NSColor {
        remaining <= 20 ? .systemRed : remaining <= 50 ? .systemBlue : .systemGreen
    }
    func label(_ window:[String:Any]) -> String {
        guard let duration=window["duration"] as? Int, duration>0 else {return window["key"] as? String == "primary" ? "主窗口" : "次窗口"}
        return duration % 1440 == 0 ? "\(duration/1440)d" : duration % 60 == 0 ? "\(duration/60)h" : "\(duration)m"
    }
    func refresh() {
        if let data=try? Data(contentsOf:root.appendingPathComponent("snapshot.json")),
           let value=(try? JSONSerialization.jsonObject(with:data)) as? [String:Any] { snapshot=value }
        let quota=snapshot["quota"] as? [String:Any] ?? [:]
        let age=Date().timeIntervalSince1970-(quota["updatedAt"] as? Double ?? 0)
        let live=quota["status"] as? String == "live" && age<120
        let windows=live ? quota["windows"] as? [[String:Any]] ?? [] : []
        item.button?.title=windows.isEmpty ? " 用量 —" : " "+windows.map{self.label($0)+" \(Int($0["remaining"] as? Double ?? 0))%"}.joined(separator:" · ")
        item.button?.setAccessibilityLabel("Codex quota monitor")
        item.button?.toolTip="Codex：账户实际报告的配额窗口；点击查看上下文和趋势"
        let values:[Double?]=windows.isEmpty ? [nil] : windows.map{$0["remaining"] as? Double}
        let image=NSImage(size:NSSize(width:values.count*11,height:18),flipped:false) { _ in
            for (index,value) in values.enumerated() {
                let x=CGFloat(index*11)
                NSColor.secondaryLabelColor.withAlphaComponent(0.2).setFill()
                NSBezierPath(roundedRect:NSRect(x:x,y:1,width:8,height:15),xRadius:2,yRadius:2).fill()
                (value.map{self.color($0)} ?? NSColor.secondaryLabelColor).setFill()
                NSBezierPath(roundedRect:NSRect(x:x+1,y:2,width:6,height:max(1,13*CGFloat(value ?? 0)/100)),xRadius:1,yRadius:1).fill()
            }
            return true
        }
        image.isTemplate=false;item.button?.image=image
        let menu=NSMenu()
        func label(_ text:String) { let entry=NSMenuItem(title:text,action:nil,keyEquivalent:"");entry.isEnabled=false;menu.addItem(entry) }
        label("Codex · 用量")
        if live {
            if windows.isEmpty {label("账户未报告周期配额窗口")}
            for window in windows {
                let remaining=window["remaining"] as? Double ?? 0
                label("\(self.label(window)) 剩余  \(Int(remaining))%")
                if let pace=window["paceDelta"] as? Double {
                    let text=abs(pace)<2 ? "符合均匀进度" : pace>0 ? "消耗快于均匀进度 \(Int(abs(pace)))pt" : "消耗慢于均匀进度 \(Int(abs(pace)))pt"
                    label(text)
                }
                if let timestamp=window["projectedExhaustAt"] as? Double {
                    let formatter=DateFormatter();formatter.dateFormat="M/d HH:mm"
                    label("按当前速度预计耗尽："+formatter.string(from:Date(timeIntervalSince1970:timestamp)))
                }
                if let timestamp=window["resetsAt"] as? Double {
                    let formatter=DateFormatter();formatter.dateFormat="M/d HH:mm"
                    label("重置："+formatter.string(from:Date(timeIntervalSince1970:timestamp)))
                }
            }
        } else {label("配额数据未更新 · 打开 Codex 后恢复采集")}
        if let usage=quota["usage"] as? [String:Any] {
            let buckets=usage["dailyUsageBuckets"] as? [[String:Any]] ?? []
            if let latest=buckets.last,let tokens=latest["tokens"] as? Double {label("最近日 Token 活动：\(Int(tokens))")}
            if let summary=usage["summary"] as? [String:Any],let lifetime=summary["lifetimeTokens"] as? Double {label("累计 Token 活动：\(Int(lifetime))")}
        }
        if let credits=quota["resetCredits"] as? [String:Any],let count=credits["availableCount"] as? Int {
            label("可用重置额度：\(count)")
            if let timestamp=credits["nextExpiresAt"] as? Double {
                let formatter=DateFormatter();formatter.dateFormat="M/d HH:mm"
                label("最近到期："+formatter.string(from:Date(timeIntervalSince1970:timestamp)))
            }
        }
        if let context=snapshot["context"] as? [String:Any],let used=context["latest_context_percent"] as? Double {
            label(String(format:"上下文已用 %.1f%%",used))
            if let model=context["model"] as? String {
                let effort=context["reasoning_effort"] as? String
                label("模型：\(model)"+(effort.map{" · 推理 \($0)"} ?? ""))
            }
        }
        if let health=snapshot["health"] as? [String:Any] {
            label("已观察压缩 \(health["count"] as? Int ?? 0) 次")
            if let after=health["after"] as? Int {label("压缩后首请求：\(after/1000)K（含系统与工具）")}
            if health["recommendHandoff"] as? Bool == true {label("建议整理交接，换新任务继续")}
        }
        menu.addItem(.separator())
        label(live ? "账户数据 \(max(0,Int(age))) 秒前更新" : "当前显示为上次采集信息")
        for (text,action) in [("查看 7 天趋势",#selector(openHistory)),("显示监控卡片",#selector(showOverlay)),("退出菜单栏",#selector(quitMenu))] {
            let entry=NSMenuItem(title:text,action:action,keyEquivalent:"");entry.target=self;menu.addItem(entry)
        }
        item.menu=menu
    }
    @objc func openHistory() {
        let url=root.appendingPathComponent("history.html")
        if FileManager.default.fileExists(atPath:url.path) {NSWorkspace.shared.open(url)}
    }
    @objc func showOverlay() {
        for path in ["/Applications/ChatGPT.app","/Applications/Codex.app"] {
            if FileManager.default.fileExists(atPath:path) {NSWorkspace.shared.open(URL(fileURLWithPath:path));break}
        }
        DispatchQueue.main.asyncAfter(deadline:.now()+1) {
            let task=Process();task.executableURL=URL(fileURLWithPath:"/usr/bin/python3")
            task.arguments=[self.root.appendingPathComponent("scripts/monitorctl.py").path,"show"]
            try? task.run()
        }
    }
    @objc func quitMenu() {
        let task=Process();task.executableURL=URL(fileURLWithPath:"/bin/launchctl")
        task.arguments=["bootout","gui/\(getuid())/local.codex-quota-menu"]
        try? task.run()
        NSApp.terminate(nil)
    }
}
let app=NSApplication.shared
app.setActivationPolicy(.accessory)
let delegate=QuotaMenu()
app.delegate=delegate
if CommandLine.arguments.contains("--check") {
    delegate.refresh()
    print(delegate.item.menu?.items.map{$0.title}.joined(separator:"\n") ?? "No menu")
    exit(0)
}
app.run()
