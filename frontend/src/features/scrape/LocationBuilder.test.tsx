import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, expect, vi } from "vitest";
import { LocationBuilder } from "./LocationBuilder";
import { useScrapeDraft } from "../../stores/useScrapeDraft";
import { renderWithProviders } from "../../test/utils";
import { GeoResolution } from "../../types";

const mockGeo: GeoResolution = {
  display_name: "HSR Layout, Bengaluru, Karnataka, India",
  boundary_kind: "admin_polygon",
  boundary_source: "osm_relation",
  geo_confidence: 0.92,
  polygon_wkt: "POLYGON((77.6 12.9, 77.7 12.9, 77.7 13.0, 77.6 13.0, 77.6 12.9))",
  centroid: [77.63, 12.91],
  bbox: [77.6, 12.9, 77.7, 13.0],
};

describe("LocationBuilder", () => {
  it("renders location input fields and resolved boundary", () => {
    useScrapeDraft.getState().setLocationField("locality", "HSR Layout");
    useScrapeDraft.getState().setLocationField("city", "Bengaluru");

    renderWithProviders(<LocationBuilder onGeoResolved={vi.fn()} resolvedGeo={mockGeo} />);

    expect(screen.getByLabelText(/locality/i)).toHaveValue("HSR Layout");
    expect(screen.getByLabelText(/^city/i)).toHaveValue("Bengaluru");
    expect(screen.getByTestId("boundary-summary")).toBeInTheDocument();
    expect(screen.getByTestId("boundary-kind")).toBeInTheDocument();
  });

  it("updates field values on typing", async () => {
    const user = userEvent.setup();
    renderWithProviders(<LocationBuilder onGeoResolved={vi.fn()} resolvedGeo={mockGeo} />);

    const localityInput = screen.getByLabelText(/locality/i);
    await user.clear(localityInput);
    await user.type(localityInput, "Koramangala");

    expect(useScrapeDraft.getState().location.locality).toBe("Koramangala");
  });
});
