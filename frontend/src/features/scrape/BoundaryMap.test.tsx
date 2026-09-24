import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi } from "vitest";
import { BoundaryMap, getProvenanceMeta } from "./BoundaryMap";
import { GeoResolution, BoundarySource } from "../../types";

describe("BoundaryMap and Provenance", () => {
  const baseGeo: GeoResolution = {
    display_name: "Whitefield, Bengaluru, Karnataka, India",
    osm_id: "7426387",
    polygon_wkt: "POLYGON((77.7 12.9, 77.8 12.9, 77.8 13.0, 77.7 13.0, 77.7 12.9))",
    boundary_kind: "admin_polygon",
    boundary_source: "osm_relation",
    centroid: [77.75, 12.96],
    bbox: [77.7, 12.9, 77.8, 13.0],
    geo_confidence: 0.95,
  };

  it("classifies all 7 boundary sources accurately", () => {
    const sources: BoundarySource[] = [
      "osm_relation",
      "osm_way",
      "overture_division_area",
      "poi_concave_hull",
      "h3_cover",
      "nominatim_bbox",
      "radius_circle",
    ];

    sources.forEach((source) => {
      const geo: GeoResolution = {
        ...baseGeo,
        boundary_source: source,
        buffer_m: 1500,
      };
      const meta = getProvenanceMeta(geo);
      expect(meta.source).toBe(source);
      expect(meta.chip).toBeTruthy();
      expect(meta.tooltip).toBeTruthy();
      expect(meta.ariaDescription).toContain("Whitefield");

      if (
        source === "osm_relation" ||
        source === "osm_way" ||
        source === "overture_division_area"
      ) {
        expect(meta.variant).toBe("good");
        expect(meta.stroke).toBe("solid");
      } else {
        expect(meta.variant).toBe("warning");
        expect(meta.stroke).toBe("dashed");
      }
    });
  });

  it("renders empty placeholder when no geo is provided", () => {
    render(<BoundaryMap geo={null} resolving={false} />);
    expect(screen.getByTestId("boundary-map-empty")).toBeInTheDocument();
    expect(
      screen.getByText(/enter location to resolve target geographic boundary/i)
    ).toBeInTheDocument();
  });

  it("renders container, aria live description and exact boundary chip for osm_relation", () => {
    render(<BoundaryMap geo={baseGeo} resolving={false} />);
    expect(screen.getByTestId("boundary-map-container")).toBeInTheDocument();
    expect(screen.getByTestId("boundary-kind")).toHaveTextContent("Exact boundary");
    expect(screen.getByTestId("boundary-summary")).toHaveTextContent("Whitefield");
    expect(screen.getByTestId("boundary-aria-announcement")).toHaveTextContent(
      "Showing exact OpenStreetMap administrative boundary for Whitefield"
    );
  });

  it("renders radius chip with km for radius_circle fallback", () => {
    const approxGeo: GeoResolution = {
      ...baseGeo,
      display_name: "Old City, Hyderabad, Telangana, India",
      boundary_kind: "buffered_point",
      boundary_source: "radius_circle",
      buffer_m: 2000,
    };
    render(<BoundaryMap geo={approxGeo} resolving={false} />);
    expect(screen.getByTestId("boundary-kind")).toHaveTextContent("~2.0 km radius");
    expect(screen.getByTestId("boundary-aria-announcement")).toHaveTextContent(
      "Showing approximate radius circle of 2.0 km for Old City"
    );
  });

  it("renders delayed spinner overlay when resolving", async () => {
    render(
      <BoundaryMap
        geo={baseGeo}
        resolving={true}
        resolvingTarget="Whitefield"
      />
    );
    await waitFor(
      () => {
        expect(
          screen.getByTestId("boundary-resolving-overlay")
        ).toBeInTheDocument();
      },
      { timeout: 500 }
    );
  });
});
