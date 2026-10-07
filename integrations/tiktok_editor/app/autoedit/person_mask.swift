import Foundation
import Vision
import CoreImage
import ImageIO

// Usage: person_mask input.jpg output.png [input2.jpg output2.png ...]
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
    let request = VNGeneratePersonSegmentationRequest()
    request.qualityLevel = .accurate
    request.outputPixelFormat = kCVPixelFormatType_OneComponent8
    request.usesCPUOnly = true
    do {
        try VNImageRequestHandler(cgImage: image).perform([request])
        guard let mask = request.results?.first?.pixelBuffer else {
            fputs("No person mask for \(input.path)\n", stderr)
            exit(4)
        }
        let raw = CIImage(cvPixelBuffer: mask)
        let ci = raw.transformed(by: CGAffineTransform(
            scaleX: CGFloat(image.width) / raw.extent.width,
            y: CGFloat(image.height) / raw.extent.height))
        try context.writePNGRepresentation(of: ci, to: output, format: .L8,
                                           colorSpace: gray, options: [:])
    } catch {
        fputs("Mask failed for \(input.path): \(error)\n", stderr)
        exit(5)
    }
}
