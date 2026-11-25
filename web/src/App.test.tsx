import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import App from "./App";

afterEach(cleanup);

describe("operator console foundation", () => {
  it("labels all placeholder operations data as synthetic", () => {
    render(<App />);

    expect(screen.getByRole("heading", { name: "Charging operations" })).toBeInTheDocument();
    expect(screen.getByText("Synthetic snapshot")).toBeInTheDocument();
    expect(screen.getByText(/not measured availability/i)).toBeInTheDocument();
    expect(screen.getByText(/deterministic demo fixtures/i)).toBeInTheDocument();
  });

  it("exposes the primary operator navigation", () => {
    render(<App />);

    const navigation = screen.getByRole("navigation", { name: "Primary navigation" });
    expect(navigation).toHaveTextContent("Overview");
    expect(navigation).toHaveTextContent("Sites");
    expect(navigation).toHaveTextContent("Chargers");
    expect(navigation).toHaveTextContent("Sessions");
    expect(navigation).toHaveTextContent("Billing");
  });
});
