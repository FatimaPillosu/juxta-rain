// Colour classes shared by the maps and legends. Lower bounds are inclusive.

// Rainfall amounts: ECMWF-style 24 h precipitation scale supplied by Fatima
// (22 Oct 2026). Colours are the pixel-sampled values already used in
// projects/irish_ffc/src/irish_ffc/rainfall_style.py; values below 0.5 mm are white.
const AMOUNT = {
  edges: [0, 0.5, 2, 5, 10, 20, 30, 40, 50, 60, 80, 100, 125, 150, 200, 300, 500, 1000, Infinity],
  colours: ["#FFFFFF", "#C0F3EE", "#74EEC7", "#11D99B", "#87CC21", "#99E90E", "#E6FF66", "#E3E30F",
            "#FFBA03", "#FF7D01", "#FE0000", "#D902FE", "#A301EB", "#5E4AE9", "#090AD6", "#0B0B6F",
            "#CCCCCC", "#666666"],
  legendFrom: 1, // the legend starts at 0.5 mm, like the reference colour bar
  units: "mm",
};

// Probabilities: the ecPoint palette of ECMWF Open Charts
// (legend of medium-point-rain-prob-24h, read from the API on 22 Oct 2026).
const PROB = {
  edges: [0, 0.5, 2.5, 4.5, 7.5, 10.5, 15.5, 20.5, 30.5, 40.5, 60.5, 80.5, 100],
  colours: ["#FFFFFF", "#93E5EF", "#03BFDB", "#08B542", "#16EF5E", "#BFEA19", "#96BC06",
            "#E08204", "#FC9916", "#F75466", "#DD42F9", "#840896"],
  legendFrom: 0,
  units: "%",
};
