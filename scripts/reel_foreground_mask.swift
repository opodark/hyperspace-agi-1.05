// SPDX-License-Identifier: Apache-2.0
import Foundation
import Vision
import CoreImage
import ImageIO

// Usage: reel_foreground_mask input.png output.png [input2.png output2.png ...]
let args = Array(CommandLine.arguments.dropFirst())
guard args.count >= 2 && args.count % 2 == 0 else {
    fputs("Expected input/output image pairs\n", stderr)
    exit(2)
}
let context = CIContext(options: [.useSoftwareRenderer: false])
let gray = CGColorSpaceCreateDeviceGray()
for index in stride(from: 0, to: args.count, by: 2) {
    let input = URL(fileURLWithPath: args[index])
    let output = URL(fileURLWithPath: args[index + 1])
    guard let source = CGImageSourceCreateWithURL(input as CFURL, nil),
          let image = CGImageSourceCreateImageAtIndex(source, 0, nil) else {
        fputs("Could not read \(input.path)\n", stderr)
        exit(3)
    }
    let handler = VNImageRequestHandler(cgImage: image)
    let request = VNGenerateForegroundInstanceMaskRequest()
    do {
        try handler.perform([request])
        guard let result = request.results?.first else {
            fputs("No foreground mask for \(input.path)\n", stderr)
            exit(4)
        }
        let mask = try result.generateScaledMaskForImage(forInstances: result.allInstances,
                                                          from: handler)
        try context.writePNGRepresentation(of: CIImage(cvPixelBuffer: mask), to: output,
                                           format: .L8, colorSpace: gray, options: [:])
    } catch {
        fputs("Foreground mask failed for \(input.path): \(error)\n", stderr)
        exit(5)
    }
}
