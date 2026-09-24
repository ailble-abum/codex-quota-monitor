import AppKit
import Foundation

struct LocalReport {
    let title: String
    let lines: [String]

    init(path: String, now: TimeInterval = Date().timeIntervalSince1970) {
        guard let data = try? Data(contentsOf: URL(fileURLWithPath: path)),
              data.count <= 4_000_000,
              let rows = (try? JSONSerialization.jsonObject(with: data)) as? [[String: Any]] else {
            title = "Codex · —"
            lines = ["本地历史未启用或不可读取"]
            return
        }
        let valid = rows.filter { row in
            guard let at = row["at"] as? Double else { return false }
            return at.isFinite && at >= now - 7 * 86400 && at <= now + 120
        }
        let latest = valid.max { ($0["at"] as? Double ?? 0) < ($1["at"] as? Double ?? 0) }
        let account = latest?["accountKey"] as? String
        let selected = valid.filter { ($0["accountKey"] as? String) == account }
        let recent = latest.flatMap { row -> Bool? in
            guard let at = row["at"] as? Double else { return nil }
            return now - at < 120
        } ?? false
        let remaining = (latest?["windows"] as? [[String: Any]] ?? []).compactMap { window -> Double? in
            guard let value = window["remaining"] as? Double,
                  value.isFinite && value >= 0 && value <= 100 else { return nil }
            return value
        }.min()
        title = recent && remaining != nil ? "Codex · \(Int(remaining!.rounded()))%" : "Codex · —"
        var current = [String]()
        if recent, let latest {
            let windows = latest["windows"] as? [[String: Any]] ?? []
            for window in windows.prefix(4) {
                guard let key = window["key"] as? String,
                      let value = window["remaining"] as? Double,
                      value.isFinite && (0...100).contains(value) else { continue }
                let duration = window["duration"] as? Double
                let label: String
                if let duration, duration.isFinite, duration > 0 {
                    label = duration >= 1440 && duration.truncatingRemainder(dividingBy: 1440) == 0
                        ? "\(Int(duration / 1440)) 天额度" : duration >= 60 && duration.truncatingRemainder(dividingBy: 60) == 0
                        ? "\(Int(duration / 60)) 小时额度" : "\(Int(duration)) 分钟额度"
                } else {
                    label = key == "primary" ? "主要额度" : key == "secondary" ? "次要额度" : "其他额度"
                }
                var line = "\(label)：剩余 \(Int(value.rounded()))%"
                if let reset = window["resetsAt"] as? Double, reset.isFinite,
                   reset >= 0 && reset <= 8.64e12 {
                    let formatter = DateFormatter()
                    formatter.dateFormat = "M月d日 HH:mm"
                    line += " · \(formatter.string(from: Date(timeIntervalSince1970: reset))) 重置"
                }
                current.append(line)
            }
            if let context = latest["context"] as? [String: Any],
               let value = context["latest_context_percent"] as? Double,
               value.isFinite && (0...100).contains(value) {
                current.append("当前上下文：\(Int(value.rounded()))%")
            }
        }
        if current.isEmpty { current = ["当前数据：暂无有效采样"] }
        var models: [String: Int] = [:]
        var projects: [String: Int] = [:]
        for row in selected {
            if let model = row["model"] as? String, model.count <= 128 {
                models[model, default: 0] += 1
            }
            if let name = row["projectLabel"] as? String, name.count <= 80,
               let key = row["projectKey"] as? String, key.count == 64 {
                projects[name, default: 0] += 1
            }
        }
        func leaders(_ values: [String: Int]) -> String {
            values.sorted { $0.value == $1.value ? $0.key < $1.key : $0.value > $1.value }
                .prefix(3).map { "\($0.key) \($0.value)" }.joined(separator: " · ")
        }
        lines = current + ["本地 7 天采样：\(selected.count)",
                 "主要模型：\(leaders(models).isEmpty ? "—" : leaders(models))",
                 "主要项目：\(leaders(projects).isEmpty ? "—" : leaders(projects))"]
    }
}

final class MenuApp: NSObject {
    private let path: String
    private var reportURL: URL { URL(fileURLWithPath: path).deletingLastPathComponent().appendingPathComponent("history.html") }
    private let item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
    private var timer: Timer?

    init(path: String) {
        self.path = path
        super.init()
        refresh()
        timer = Timer.scheduledTimer(withTimeInterval: 15, repeats: true) { [weak self] _ in
            self?.refresh()
        }
    }

    private func refresh() {
        let report = LocalReport(path: path)
        item.button?.title = report.title
        let menu = NSMenu()
        for line in report.lines {
            let row = NSMenuItem(title: line, action: nil, keyEquivalent: "")
            row.isEnabled = true
            menu.addItem(row)
        }
        let openReport = NSMenuItem(title: "打开本地七天报告", action: #selector(showReport), keyEquivalent: "")
        openReport.target = self
        openReport.isEnabled = FileManager.default.fileExists(atPath: reportURL.path)
        menu.addItem(openReport)
        menu.addItem(.separator())
        let quit = NSMenuItem(title: "退出 V2 菜单栏", action: #selector(quitApp), keyEquivalent: "q")
        quit.target = self
        menu.addItem(quit)
        item.menu = menu
    }

    @objc private func quitApp() { NSApplication.shared.terminate(nil) }
    @objc private func showReport() { NSWorkspace.shared.open(reportURL) }
}

guard CommandLine.arguments.count == 3,
      ["--report", "--run"].contains(CommandLine.arguments[1]) else {
    fputs("usage: QuotaMenu --report|--run /absolute/history.json\n", stderr)
    exit(2)
}
let path = CommandLine.arguments[2]
guard path.hasPrefix("/") else { exit(2) }
if CommandLine.arguments[1] == "--report" {
    let report = LocalReport(path: path)
    print(([report.title] + report.lines).joined(separator: "\n"))
} else {
    let app = NSApplication.shared
    app.setActivationPolicy(.accessory)
    let menuApp = MenuApp(path: path)
    withExtendedLifetime(menuApp) { app.run() }
}
