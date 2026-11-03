// Use librsvg's Cairo renderer so text shaping matches the layout preflight.
imports.gi.versions.Rsvg = '2.0'
const { Rsvg } = imports.gi
const Cairo = imports.cairo
const [source, output, width, height] = ARGV
const viewport = new Rsvg.Rectangle({ x: 0, y: 0, width: Number(width), height: Number(height) })
const drawing = Rsvg.Handle.new_from_file(source)
drawing.set_dpi(72)
const surface = new Cairo.PDFSurface(output, viewport.width, viewport.height)
drawing.render_document(new Cairo.Context(surface), viewport)
surface.finish()
