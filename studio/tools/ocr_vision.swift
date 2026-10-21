// Texterkennung mit Apple Vision (macOS) für alle PNG/JPG eines Ordners. Wird von "ms zerlegen" benutzt.
// Aufruf: ocr_vision <ordner> [sprachen, z. B. de-DE,en-US]   (ohne Sprachen: automatische Erkennung ab macOS 13)
// Ausgabe: eine JSON-Zeile pro Bild:
//   {"datei": "000012.png", "breite": W, "hoehe": H,
//    "obs": [{"text": "…", "conf": 0.98, "box": [x, y, w, h], "woerter": [{"w": "…", "box": [x, y, w, h]}]}]}
// Boxen in Pixeln des Bildes, Ursprung oben links (Vision rechnet unten links, das wird hier umgerechnet).
import Foundation
import ImageIO
import Vision

let argumente = CommandLine.arguments
guard argumente.count >= 2 else {
    FileHandle.standardError.write("Aufruf: ocr_vision <ordner> [sprachen]\n".data(using: .utf8)!)
    exit(1)
}
let ordner = URL(fileURLWithPath: argumente[1])
let sprachen: [String] = argumente.count >= 3 ? argumente[2].split(separator: ",").map { String($0) } : []
let dateien = ((try? FileManager.default.contentsOfDirectory(atPath: ordner.path)) ?? [])
    .filter { $0.lowercased().hasSuffix(".png") || $0.lowercased().hasSuffix(".jpg") }
    .sorted()

func pixel(_ r: CGRect, _ w: Int, _ h: Int) -> [Double] {
    let bw: Double = Double(w)
    let bh: Double = Double(h)
    let x: Double = Double(r.minX) * bw
    let y: Double = (1.0 - Double(r.maxY)) * bh
    let breite: Double = Double(r.width) * bw
    let hoehe: Double = Double(r.height) * bh
    return [x.rounded(), y.rounded(), breite.rounded(), hoehe.rounded()]
}

for datei in dateien {
    let url = ordner.appendingPathComponent(datei)
    guard let quelle = CGImageSourceCreateWithURL(url as CFURL, nil),
          let bild = CGImageSourceCreateImageAtIndex(quelle, 0, nil) else { continue }
    let w = bild.width, h = bild.height
    let anfrage = VNRecognizeTextRequest()
    anfrage.recognitionLevel = .accurate
    anfrage.usesLanguageCorrection = false
    if !sprachen.isEmpty {
        anfrage.recognitionLanguages = sprachen
    } else if #available(macOS 13.0, *) {
        anfrage.automaticallyDetectsLanguage = true
    }
    let handler = VNImageRequestHandler(cgImage: bild, options: [:])
    try? handler.perform([anfrage])
    var obs: [[String: Any]] = []
    for o in (anfrage.results ?? []) {
        guard let kandidat = o.topCandidates(1).first else { continue }
        let text = kandidat.string
        var woerter: [[String: Any]] = []
        text.enumerateSubstrings(in: text.startIndex..<text.endIndex, options: .byWords) { teil, bereich, _, _ in
            if let teil = teil, let bb = try? kandidat.boundingBox(for: bereich) {
                let wort: [String: Any] = ["w": teil, "box": pixel(bb.boundingBox, w, h)]
                woerter.append(wort)
            }
        }
        let eintrag: [String: Any] = ["text": text, "conf": Double(kandidat.confidence), "box": pixel(o.boundingBox, w, h),
                                      "woerter": woerter]
        obs.append(eintrag)
    }
    let zeile: [String: Any] = ["datei": datei, "breite": w, "hoehe": h, "obs": obs]
    if let daten = try? JSONSerialization.data(withJSONObject: zeile), let s = String(data: daten, encoding: .utf8) {
        print(s)
        fflush(stdout)
    }
}
