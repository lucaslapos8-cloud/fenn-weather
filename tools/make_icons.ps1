# Draws the plugin's weather icons (icons\lg\*.png, icons\sm\*.png) with WPF:
# soft 3D clouds, glowing sun and moon, rain, snow, lightning and fog.
# The PNGs are already in the repo; run this only to change how they look:
#   powershell -NoProfile -STA -ExecutionPolicy Bypass -File tools\make_icons.ps1
# ASCII only (PowerShell 5.1 reads BOM-less files as ANSI).
param([string]$Out = (Join-Path (Split-Path -Parent $PSScriptRoot) "icons"), [string]$Sheet = "")

Add-Type -ReferencedAssemblies PresentationFramework, PresentationCore, WindowsBase, System.Xaml -TypeDefinition @'
using System;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Effects;
using System.Windows.Media.Imaging;

namespace FennWeather {
public static class Icons {
    // Everything is drawn on a 256 x 256 board, rendered at 512 and scaled down.
    const double Board = 256;

    static Color C(string hex, double a = 1) {
        var c = (Color)ColorConverter.ConvertFromString(hex);
        c.A = (byte)Math.Round(255 * a);
        return c;
    }

    static ContainerVisual root;

    static DrawingContext Layer(double blur = 0, double opacity = 1) {
        var v = new DrawingVisual();
        if (blur > 0) v.Effect = new BlurEffect { Radius = blur * 2, KernelType = KernelType.Gaussian, RenderingBias = RenderingBias.Quality };
        v.Opacity = opacity;
        root.Children.Add(v);
        var dc = v.RenderOpen();
        dc.PushTransform(new ScaleTransform(2, 2));
        return dc;
    }

    static void Done(DrawingContext dc) { dc.Pop(); dc.Close(); }

    // ---- shapes

    static Geometry CloudShape(double x, double y, double w) {
        double h = w * 0.6;
        Geometry g = new RectangleGeometry(new Rect(x, y + h * 0.48, w, h * 0.52), h * 0.26, h * 0.26);
        g = Geometry.Combine(g, new EllipseGeometry(new Point(x + w * 0.30, y + h * 0.58), w * 0.20, w * 0.20), GeometryCombineMode.Union, null);
        g = Geometry.Combine(g, new EllipseGeometry(new Point(x + w * 0.57, y + h * 0.42), w * 0.27, w * 0.27), GeometryCombineMode.Union, null);
        g = Geometry.Combine(g, new EllipseGeometry(new Point(x + w * 0.80, y + h * 0.67), w * 0.16, w * 0.16), GeometryCombineMode.Union, null);
        return g;
    }

    // tone 0 = white, 1 = light grey, 2 = rain grey, 3 = storm
    static readonly string[][] Tones = {
        new[] { "#FFFFFF", "#F1F4F9", "#C5CEDB" },
        new[] { "#E9EDF3", "#D2D8E2", "#A4AEBD" },
        new[] { "#D3D9E2", "#B4BCC8", "#848E9D" },
        new[] { "#A9B1BE", "#868F9D", "#5D6574" },
    };

    static void Cloud(double x, double y, double w, int tone, Point? light = null, string lightColor = "#FFB347") {
        var shape = CloudShape(x, y, w);
        // soft shadow under it
        var dc = Layer(w * 0.05, 0.45);
        dc.PushTransform(new TranslateTransform(0, w * 0.045));
        dc.DrawGeometry(new SolidColorBrush(C("#000000", 0.55)), null, shape);
        dc.Pop();
        Done(dc);

        dc = Layer();
        var t = Tones[tone];
        var fill = new LinearGradientBrush { StartPoint = new Point(0.5, 0), EndPoint = new Point(0.5, 1) };
        fill.GradientStops.Add(new GradientStop(C(t[0]), 0.0));
        fill.GradientStops.Add(new GradientStop(C(t[1]), 0.55));
        fill.GradientStops.Add(new GradientStop(C(t[2]), 1.0));
        dc.DrawGeometry(fill, null, shape);
        dc.PushClip(shape);
        // warm light from the sun behind it
        if (light.HasValue) {
            var warm = new RadialGradientBrush { GradientOrigin = new Point(0.5, 0.5) };
            warm.GradientStops.Add(new GradientStop(C(lightColor, 0.55), 0));
            warm.GradientStops.Add(new GradientStop(C(lightColor, 0.18), 0.55));
            warm.GradientStops.Add(new GradientStop(C(lightColor, 0), 1));
            dc.DrawEllipse(warm, null, light.Value, w * 0.42, w * 0.42);
        }
        // a glossy highlight along the top
        var gloss = new RadialGradientBrush { GradientOrigin = new Point(0.5, 0.5) };
        gloss.GradientStops.Add(new GradientStop(C("#FFFFFF", 0.65), 0));
        gloss.GradientStops.Add(new GradientStop(C("#FFFFFF", 0), 1));
        dc.DrawEllipse(gloss, null, new Point(x + w * 0.50, y + w * 0.10), w * 0.30, w * 0.16);
        // a slightly darker inner edge at the bottom
        var edge = new LinearGradientBrush { StartPoint = new Point(0.5, 0), EndPoint = new Point(0.5, 1) };
        edge.GradientStops.Add(new GradientStop(C("#28324A", 0), 0.70));
        edge.GradientStops.Add(new GradientStop(C("#28324A", 0.22), 1));
        dc.DrawRectangle(edge, null, new Rect(x, y - w * 0.05, w, w * 0.66));
        dc.Pop();
        Done(dc);
    }

    static void Sun(double cx, double cy, double r) {
        var dc = Layer(r * 0.55, 0.75);
        dc.DrawEllipse(new SolidColorBrush(C("#FF9A1F", 0.9)), null, new Point(cx, cy), r * 1.12, r * 1.12);
        Done(dc);
        dc = Layer();
        var body = new RadialGradientBrush { GradientOrigin = new Point(0.38, 0.32), Center = new Point(0.45, 0.42), RadiusX = 0.65, RadiusY = 0.65 };
        body.GradientStops.Add(new GradientStop(C("#FFE38A"), 0));
        body.GradientStops.Add(new GradientStop(C("#FFB72E"), 0.55));
        body.GradientStops.Add(new GradientStop(C("#FF8C0A"), 1));
        dc.DrawEllipse(body, null, new Point(cx, cy), r, r);
        Done(dc);
    }

    static void Moon(double cx, double cy, double r) {
        var shape = Geometry.Combine(new EllipseGeometry(new Point(cx, cy), r, r),
            new EllipseGeometry(new Point(cx + r * 0.52, cy - r * 0.30), r * 0.80, r * 0.80), GeometryCombineMode.Exclude, null);
        var dc = Layer(r * 0.45, 0.6);
        dc.DrawGeometry(new SolidColorBrush(C("#FFE7A3", 0.85)), null, shape);
        Done(dc);
        dc = Layer();
        var body = new LinearGradientBrush { StartPoint = new Point(0.2, 0.1), EndPoint = new Point(0.8, 1) };
        body.GradientStops.Add(new GradientStop(C("#FFF9E3"), 0));
        body.GradientStops.Add(new GradientStop(C("#FBE3A0"), 0.6));
        body.GradientStops.Add(new GradientStop(C("#EFC86A"), 1));
        dc.DrawGeometry(body, null, shape);
        Done(dc);
    }

    static void Star(double cx, double cy, double s) {
        var g = new StreamGeometry();
        using (var c = g.Open()) {
            double k = s * 0.22;
            c.BeginFigure(new Point(cx, cy - s), true, true);
            c.QuadraticBezierTo(new Point(cx + k, cy - k), new Point(cx + s, cy), true, true);
            c.QuadraticBezierTo(new Point(cx + k, cy + k), new Point(cx, cy + s), true, true);
            c.QuadraticBezierTo(new Point(cx - k, cy + k), new Point(cx - s, cy), true, true);
            c.QuadraticBezierTo(new Point(cx - k, cy - k), new Point(cx, cy - s), true, true);
        }
        var dc = Layer(s * 0.5, 0.7);
        dc.DrawGeometry(new SolidColorBrush(C("#FFF1BF")), null, g);
        Done(dc);
        dc = Layer();
        dc.DrawGeometry(new SolidColorBrush(C("#FFF6D8")), null, g);
        Done(dc);
    }

    static Pen RoundPen(Brush b, double w) {
        return new Pen(b, w) { StartLineCap = PenLineCap.Round, EndLineCap = PenLineCap.Round, LineJoin = PenLineJoin.Round };
    }

    static void Drops(double[] xs, double y, double len, double width, string top = "#9BE3FF", string bottom = "#2E9BF0") {
        var dc = Layer(width * 0.9, 0.75);
        foreach (var x in xs) dc.DrawLine(RoundPen(new SolidColorBrush(C("#3FB4FF")), width * 1.2), new Point(x, y), new Point(x - len * 0.38, y + len));
        Done(dc);
        dc = Layer();
        foreach (var x in xs) {
            var b = new LinearGradientBrush(C(top), C(bottom), new Point(0.5, 0), new Point(0.5, 1)) { MappingMode = BrushMappingMode.RelativeToBoundingBox };
            dc.DrawLine(RoundPen(b, width), new Point(x, y), new Point(x - len * 0.38, y + len));
        }
        Done(dc);
    }

    static void Flake(double cx, double cy, double s, DrawingContext dc, Brush b, double w) {
        var pen = RoundPen(b, w);
        for (int i = 0; i < 3; i++) {
            double a = Math.PI / 2 + i * Math.PI / 3;
            var d = new Vector(Math.Cos(a) * s, Math.Sin(a) * s);
            dc.DrawLine(pen, new Point(cx, cy) - d, new Point(cx, cy) + d);
            foreach (var sign in new[] { -1.0, 1.0 }) {
                var tip = new Point(cx, cy) + d * sign * 0.62;
                var arm = d * sign * 0.32;
                var n = new Vector(-arm.Y, arm.X);
                dc.DrawLine(pen, tip, tip + arm * 0.9 + n * 0.9);
                dc.DrawLine(pen, tip, tip + arm * 0.9 - n * 0.9);
            }
        }
    }

    static void Flakes(double[][] at) {
        var dc = Layer(6, 0.8);
        foreach (var f in at) Flake(f[0], f[1], f[2], dc, new SolidColorBrush(C("#59D2FF")), f[2] * 0.28);
        Done(dc);
        dc = Layer();
        foreach (var f in at) Flake(f[0], f[1], f[2], dc, new SolidColorBrush(C("#F2FCFF")), f[2] * 0.2);
        Done(dc);
    }

    static void Dots(double[][] at, string color) {
        var dc = Layer(4, 0.7);
        foreach (var d in at) dc.DrawEllipse(new SolidColorBrush(C(color)), null, new Point(d[0], d[1]), d[2] * 1.3, d[2] * 1.3);
        Done(dc);
        dc = Layer();
        foreach (var d in at) dc.DrawEllipse(new SolidColorBrush(C("#F4FBFF")), null, new Point(d[0], d[1]), d[2], d[2]);
        Done(dc);
    }

    static void Bolt(double ox, double oy, double s) {
        var g = new StreamGeometry();
        using (var c = g.Open()) {
            Func<double, double, Point> P = (x, y) => new Point(ox + x * s, oy + y * s);
            c.BeginFigure(P(16, 0), true, true);
            c.PolyLineTo(new[] { P(-14, 50), P(4, 50), P(-10, 100), P(34, 34), P(14, 34), P(30, 0) }, true, true);
        }
        var dc = Layer(14 * s, 0.9);
        dc.DrawGeometry(new SolidColorBrush(C("#FFA41C")), null, g);
        Done(dc);
        dc = Layer();
        var b = new LinearGradientBrush(C("#FFF07A"), C("#FF9A12"), new Point(0.5, 0), new Point(0.5, 1));
        dc.DrawGeometry(b, RoundPen(new SolidColorBrush(C("#FFC93C")), 1.5), g);
        Done(dc);
    }

    static void Fog(double[][] lines) {
        var dc = Layer();
        foreach (var l in lines) {
            var b = new LinearGradientBrush { StartPoint = new Point(0, 0.5), EndPoint = new Point(1, 0.5) };
            b.GradientStops.Add(new GradientStop(C("#E6ECF4", 0.35), 0));
            b.GradientStops.Add(new GradientStop(C("#F4F7FB", 0.95), 0.5));
            b.GradientStops.Add(new GradientStop(C("#E6ECF4", 0.35), 1));
            dc.DrawLine(RoundPen(b, 13), new Point(l[0], l[1]), new Point(l[2], l[1]));
        }
        Done(dc);
    }


    // ---- icons for the Glossy widgets

    static void Glossy(DrawingContext dc, Geometry shape, double x, double y, double rx, double ry) {
        // a soft white shine in the upper left of a shape
        dc.PushClip(shape);
        var gloss = new RadialGradientBrush();
        gloss.GradientStops.Add(new GradientStop(C("#FFFFFF", 0.7), 0));
        gloss.GradientStops.Add(new GradientStop(C("#FFFFFF", 0), 1));
        dc.DrawEllipse(gloss, null, new Point(x, y), rx, ry);
        dc.Pop();
    }

    static void Shape(Geometry shape, string top, string bottom, string glow, double blur) {
        var dc = Layer(blur, 0.65);
        dc.DrawGeometry(new SolidColorBrush(C(glow)), null, shape);
        Done(dc);
        dc = Layer();
        dc.DrawGeometry(new LinearGradientBrush(C(top), C(bottom), new Point(0.3, 0), new Point(0.7, 1)), null, shape);
        Done(dc);
    }

    static Geometry DropShape(double cx, double top, double h) {
        double w = h * 0.72;
        var g = new StreamGeometry();
        using (var c = g.Open()) {
            c.BeginFigure(new Point(cx, top), true, true);
            c.BezierTo(new Point(cx + w * 0.16, top + h * 0.24), new Point(cx + w * 0.5, top + h * 0.44), new Point(cx + w * 0.5, top + h * 0.66), true, true);
            c.ArcTo(new Point(cx - w * 0.5, top + h * 0.66), new Size(w * 0.5, h * 0.34), 0, false, SweepDirection.Clockwise, true, true);
            c.BezierTo(new Point(cx - w * 0.5, top + h * 0.44), new Point(cx - w * 0.16, top + h * 0.24), new Point(cx, top), true, true);
        }
        g.Freeze();
        return g;
    }

    static void BigDrop() {
        var shape = DropShape(128, 26, 204);
        Shape(shape, "#A8E8FF", "#2387E8", "#3FB4FF", 14);
        var dc = Layer();
        Glossy(dc, shape, 98, 150, 26, 40);
        dc.PushClip(shape);
        var edge = new LinearGradientBrush(C("#0B3E8A", 0), C("#0B3E8A", 0.35), new Point(0.5, 0.6), new Point(0.5, 1));
        dc.DrawRectangle(edge, null, new Rect(0, 0, 256, 256));
        dc.Pop();
        Done(dc);
    }

    static void WindIcon() {
        var g = new StreamGeometry();
        using (var c = g.Open()) {
            c.BeginFigure(new Point(34, 100), false, false);
            c.LineTo(new Point(160, 100), true, true);
            c.ArcTo(new Point(160, 52), new Size(24, 24), 0, false, SweepDirection.Counterclockwise, true, true);
            c.BeginFigure(new Point(26, 140), false, false);
            c.LineTo(new Point(192, 140), true, true);
            c.ArcTo(new Point(192, 192), new Size(26, 26), 0, false, SweepDirection.Clockwise, true, true);
            c.BeginFigure(new Point(56, 180), false, false);
            c.LineTo(new Point(132, 180), true, true);
        }
        g.Freeze();
        var dc = Layer(12, 0.6);
        dc.DrawGeometry(null, RoundPen(new SolidColorBrush(C("#3FB4FF")), 22), g);
        Done(dc);
        dc = Layer(6, 0.35);
        dc.PushTransform(new TranslateTransform(0, 6));
        dc.DrawGeometry(null, RoundPen(new SolidColorBrush(C("#0B2A55")), 18), g);
        dc.Pop();
        Done(dc);
        dc = Layer();
        var b = new LinearGradientBrush(C("#FFFFFF"), C("#A9DBFF"), new Point(0, 0), new Point(1, 1));
        dc.DrawGeometry(null, RoundPen(b, 17), g);
        dc.DrawGeometry(null, RoundPen(new SolidColorBrush(C("#FFFFFF", 0.55)), 5), g);
        Done(dc);
    }

    static void HalfSun(double cx, double cy, double r, bool warm) {
        var clip = new RectangleGeometry(new Rect(0, 0, Board, cy));
        var dc = Layer(r * 0.5, 0.75);
        dc.PushClip(clip);
        dc.DrawEllipse(new SolidColorBrush(C(warm ? "#FF7A1F" : "#FF9A1F", 0.9)), null, new Point(cx, cy), r * 1.15, r * 1.15);
        dc.Pop();
        Done(dc);
        dc = Layer();
        dc.PushClip(clip);
        var body = new RadialGradientBrush { GradientOrigin = new Point(0.4, 0.3), Center = new Point(0.45, 0.4), RadiusX = 0.65, RadiusY = 0.65 };
        body.GradientStops.Add(new GradientStop(C("#FFE38A"), 0));
        body.GradientStops.Add(new GradientStop(C(warm ? "#FF9A3C" : "#FFB72E"), 0.55));
        body.GradientStops.Add(new GradientStop(C(warm ? "#F0622A" : "#FF8C0A"), 1));
        dc.DrawEllipse(body, null, new Point(cx, cy), r, r);
        dc.Pop();
        var rays = new SolidColorBrush(C("#FFB52E"));
        for (int i = 0; i < 5; i++) {
            double a = Math.PI + Math.PI * (i + 0.5) / 5;
            dc.DrawLine(RoundPen(rays, 11), new Point(cx + Math.Cos(a) * r * 1.3, cy + Math.Sin(a) * r * 1.3),
                        new Point(cx + Math.Cos(a) * r * 1.62, cy + Math.Sin(a) * r * 1.62));
        }
        Done(dc);
    }

    static void Horizon(double cy, bool up) {
        var dc = Layer();
        var water = new LinearGradientBrush(C("#E9F5FF"), C("#8FC4F0"), new Point(0, 0), new Point(0, 1));
        double[] widths = { 196, 140, 84 };
        for (int i = 0; i < 3; i++) {
            double w = widths[i], y = cy + 6 + i * 22;
            dc.DrawRoundedRectangle(water, null, new Rect(128 - w / 2, y, w, 13), 6.5, 6.5);
        }
        // the arrow above the sun
        var pen = RoundPen(new LinearGradientBrush(C("#FFFFFF"), C("#DCE7F5"), new Point(0, 0), new Point(0, 1)), 14);
        double a0 = 22, a1 = 70;
        dc.DrawLine(pen, new Point(128, a0), new Point(128, a1));
        double tip = up ? a0 : a1, back = up ? a0 + 20 : a1 - 20;
        dc.DrawLine(pen, new Point(108, back), new Point(128, tip));
        dc.DrawLine(pen, new Point(148, back), new Point(128, tip));
        Done(dc);
    }

    static void UmbrellaIcon() {
        var canopy = new StreamGeometry();
        using (var c = canopy.Open()) {
            c.BeginFigure(new Point(26, 128), true, true);
            c.ArcTo(new Point(230, 128), new Size(102, 86), 0, false, SweepDirection.Clockwise, true, true);
            for (int i = 0; i < 3; i++) {
                double x0 = 230 - i * 68, x1 = x0 - 68;
                c.ArcTo(new Point(x1, 128), new Size(34, 16), 0, false, SweepDirection.Counterclockwise, true, true);
            }
        }
        canopy.Freeze();
        // handle first, under the canopy
        var dc = Layer();
        var metal = RoundPen(new LinearGradientBrush(C("#E3E8EF"), C("#8D97A6"), new Point(0, 0), new Point(1, 0)), 12);
        var handle = new StreamGeometry();
        using (var c = handle.Open()) {
            c.BeginFigure(new Point(128, 120), false, false);
            c.LineTo(new Point(128, 206), true, true);
            c.ArcTo(new Point(96, 206), new Size(16, 16), 0, false, SweepDirection.Clockwise, true, true);
        }
        dc.DrawGeometry(null, metal, handle);
        dc.DrawLine(RoundPen(new SolidColorBrush(C("#8D97A6")), 10), new Point(128, 30), new Point(128, 46));
        Done(dc);
        Shape(canopy, "#9C8CFF", "#4A39D8", "#6E5CFF", 14);
        dc = Layer();
        Glossy(dc, canopy, 92, 66, 60, 32);
        Done(dc);
    }

    static void ThermometerIcon() {
        var tube = new RectangleGeometry(new Rect(104, 22, 48, 170), 24, 24);
        var glass = Geometry.Combine(tube, new EllipseGeometry(new Point(128, 192), 40, 40), GeometryCombineMode.Union, null);
        Shape(glass, "#FFFFFF", "#C9D5E4", "#7FB2FF", 10);
        var liquid = Geometry.Combine(new RectangleGeometry(new Rect(118, 82, 20, 112), 10, 10),
                                      new EllipseGeometry(new Point(128, 192), 27, 27), GeometryCombineMode.Union, null);
        Shape(liquid, "#FF8A7A", "#E0261B", "#FF4B3A", 8);
        var dc = Layer();
        Glossy(dc, glass, 114, 70, 10, 60);
        Glossy(dc, liquid, 118, 182, 10, 10);
        var tick = RoundPen(new SolidColorBrush(C("#8C99AB")), 5);
        for (int i = 0; i < 4; i++) dc.DrawLine(tick, new Point(160, 50 + i * 26), new Point(176, 50 + i * 26));
        Done(dc);
    }

    static void LeafIcon() {
        var leaf = new StreamGeometry();
        using (var c = leaf.Open()) {
            c.BeginFigure(new Point(50, 210), true, true);
            c.BezierTo(new Point(46, 110), new Point(120, 46), new Point(214, 40), true, true);
            c.BezierTo(new Point(218, 132), new Point(156, 206), new Point(50, 210), true, true);
        }
        leaf.Freeze();
        Shape(leaf, "#A6EE8A", "#22994E", "#3FCB6A", 12);
        var dc = Layer();
        Glossy(dc, leaf, 108, 92, 44, 30);
        dc.DrawLine(RoundPen(new SolidColorBrush(C("#FFFFFF", 0.55)), 7), new Point(62, 198), new Point(188, 72));
        var vein = RoundPen(new SolidColorBrush(C("#FFFFFF", 0.35)), 4);
        dc.DrawLine(vein, new Point(110, 150), new Point(96, 112));
        dc.DrawLine(vein, new Point(140, 120), new Point(130, 82));
        dc.DrawLine(vein, new Point(118, 142), new Point(158, 150));
        dc.DrawLine(vein, new Point(150, 110), new Point(186, 116));
        Done(dc);
    }

    // ---- the icons

    static void Draw(string name) {
        switch (name) {
            case "clear-day":
                Sun(128, 128, 70);
                break;
            case "clear-night":
                Moon(120, 132, 76);
                Star(188, 66, 16); Star(206, 128, 10); Star(160, 40, 8);
                break;
            case "mostly-day":
                Sun(140, 108, 62);
                Cloud(34, 136, 132, 0, new Point(150, 120));
                break;
            case "mostly-night":
                Moon(146, 104, 62);
                Star(212, 58, 10);
                Cloud(30, 136, 132, 0, new Point(150, 120), "#FFE7A3");
                break;
            case "partly-day":
                Sun(160, 96, 54);
                Cloud(26, 92, 190, 0, new Point(170, 96));
                break;
            case "partly-night":
                Moon(166, 92, 52);
                Star(218, 150, 8);
                Cloud(26, 92, 190, 0, new Point(170, 96), "#FFE7A3");
                break;
            case "cloudy":
                Cloud(28, 72, 200, 0);
                break;
            case "overcast":
                Cloud(84, 52, 150, 2);
                Cloud(22, 98, 186, 1);
                break;
            case "fog":
                Cloud(36, 36, 184, 1);
                Fog(new[] { new double[] { 40, 172, 216 }, new double[] { 62, 198, 196 }, new double[] { 50, 224, 170 } });
                break;
            case "drizzle":
                Cloud(30, 40, 196, 1);
                Drops(new double[] { 92, 136, 180 }, 176, 26, 9);
                break;
            case "rain":
                Cloud(30, 40, 196, 2);
                Drops(new double[] { 82, 124, 166, 208 }, 172, 44, 10);
                break;
            case "heavy-rain":
                Cloud(84, 22, 150, 3);
                Cloud(24, 54, 190, 2);
                Drops(new double[] { 70, 106, 142, 178, 214 }, 182, 54, 10);
                break;
            case "showers-day":
                Sun(170, 70, 44);
                Cloud(26, 58, 190, 1, new Point(176, 70));
                Drops(new double[] { 92, 136, 180 }, 186, 40, 10);
                break;
            case "showers-night":
                Moon(174, 66, 42);
                Cloud(26, 58, 190, 1, new Point(176, 70), "#FFE7A3");
                Drops(new double[] { 92, 136, 180 }, 186, 40, 10);
                break;
            case "sleet":
                Cloud(30, 40, 196, 1);
                Drops(new double[] { 92, 172 }, 174, 40, 10);
                Flakes(new[] { new double[] { 134, 204, 20 } });
                break;
            case "snow":
                Cloud(30, 40, 196, 0);
                Flakes(new[] { new double[] { 86, 196, 20 }, new double[] { 172, 188, 24 } });
                Dots(new[] { new double[] { 130, 214, 6 }, new double[] { 126, 178, 4 } }, "#59D2FF");
                break;
            case "heavy-snow":
                Cloud(30, 30, 196, 1);
                Flakes(new[] { new double[] { 76, 186, 20 }, new double[] { 136, 210, 24 }, new double[] { 196, 182, 20 } });
                Dots(new[] { new double[] { 106, 228, 5 }, new double[] { 168, 236, 5 }, new double[] { 104, 168, 4 } }, "#59D2FF");
                break;
            case "thunder":
                Cloud(84, 20, 150, 3);
                Cloud(24, 50, 190, 2);
                Bolt(104, 150, 0.92);
                Drops(new double[] { 76, 196 }, 176, 38, 9);
                break;
            case "hail":
                Cloud(30, 40, 196, 2);
                Drops(new double[] { 84, 168 }, 170, 36, 9);
                Dots(new[] { new double[] { 128, 190, 9 }, new double[] { 108, 226, 8 }, new double[] { 196, 222, 8 } }, "#7FD6FF");
                break;
            case "drop": BigDrop(); break;
            case "wind": WindIcon(); break;
            case "sunrise": HalfSun(128, 168, 56, false); Horizon(168, true); break;
            case "sunset": HalfSun(128, 168, 56, true); Horizon(168, false); break;
            case "umbrella": UmbrellaIcon(); break;
            case "thermometer": ThermometerIcon(); break;
            case "leaf": LeafIcon(); break;
        }
    }

    public static readonly string[] Names = {
        "clear-day", "clear-night", "mostly-day", "mostly-night", "partly-day", "partly-night",
        "cloudy", "overcast", "fog", "drizzle", "rain", "heavy-rain", "showers-day", "showers-night",
        "sleet", "snow", "heavy-snow", "thunder", "hail",
        "drop", "wind", "sunrise", "sunset", "umbrella", "thermometer", "leaf",
    };

    static BitmapSource Big(string name) {
        root = new ContainerVisual();
        Draw(name);
        var rtb = new RenderTargetBitmap(512, 512, 96, 96, PixelFormats.Pbgra32);
        rtb.Render(root);
        rtb.Freeze();
        return rtb;
    }

    static void Save(BitmapSource src, int size, string path) {
        var img = new Image { Source = src, Width = size, Height = size, Stretch = Stretch.Fill };
        RenderOptions.SetBitmapScalingMode(img, BitmapScalingMode.HighQuality);
        img.Measure(new Size(size, size));
        img.Arrange(new Rect(0, 0, size, size));
        var rtb = new RenderTargetBitmap(size, size, 96, 96, PixelFormats.Pbgra32);
        rtb.Render(img);
        var enc = new PngBitmapEncoder();
        enc.Frames.Add(BitmapFrame.Create(rtb));
        Directory.CreateDirectory(Path.GetDirectoryName(path));
        using (var f = File.Create(path)) enc.Save(f);
    }

    public static void Run(string outDir) {
        foreach (var n in Names) {
            var big = Big(n);
            Save(big, 160, Path.Combine(outDir, "lg", n + ".png"));
            Save(big, 64, Path.Combine(outDir, "sm", n + ".png"));
        }
    }

    // A dark preview sheet of every icon, to look at them together.
    public static void Sheet(string outDir, string path) {
        int cols = 5, cell = 180;
        var names = Names;
        int rows = (names.Length + cols - 1) / cols;
        var dv = new DrawingVisual();
        using (var dc = dv.RenderOpen()) {
            dc.DrawRectangle(new SolidColorBrush(C("#0B0D10")), null, new Rect(0, 0, cols * cell, rows * cell));
            for (int i = 0; i < names.Length; i++) {
                var bmp = new BitmapImage();
                bmp.BeginInit();
                bmp.CacheOption = BitmapCacheOption.OnLoad;
                bmp.UriSource = new Uri(Path.Combine(outDir, "lg", names[i] + ".png"));
                bmp.EndInit();
                double x = (i % cols) * cell + 10, y = (i / cols) * cell + 4;
                dc.DrawImage(bmp, new Rect(x, y, 160, 160));
                var ft = new FormattedText(names[i], System.Globalization.CultureInfo.InvariantCulture, FlowDirection.LeftToRight,
                    new Typeface("Segoe UI"), 12, new SolidColorBrush(C("#8A93A0")), 1.0);
                dc.DrawText(ft, new Point(x, y + 158));
            }
        }
        var rtb = new RenderTargetBitmap(cols * cell, rows * cell, 96, 96, PixelFormats.Pbgra32);
        rtb.Render(dv);
        var enc = new PngBitmapEncoder();
        enc.Frames.Add(BitmapFrame.Create(rtb));
        using (var f = File.Create(path)) enc.Save(f);
    }
}
}
'@

[FennWeather.Icons]::Run($Out)
if ($Sheet) { [FennWeather.Icons]::Sheet($Out, $Sheet) }
Write-Output "icons written to $Out"
