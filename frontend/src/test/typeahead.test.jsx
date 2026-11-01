import { useState } from "react";
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { rankMatches, splitMatch } from "../utils/typeahead";
import SkillInput from "../components/profile/SkillInput";
import RoleInput from "../components/profile/RoleInput";

const CATALOG = [
  { name: "react", aliases: ["reactjs", "react.js"] },
  { name: "redux", aliases: [] },
  { name: "javascript", aliases: ["js", "es6"] },
  { name: "sap fico", aliases: ["fico"] },
  { name: "jsp", aliases: [] },
  { name: "python", aliases: [] },
  { name: "node.js", aliases: ["nodejs"] },
];
const ITEMS = CATALOG.map((s) => ({ label: s.name, terms: s.aliases }));
const labels = (q, opts) => rankMatches(q, ITEMS, opts).map((h) => h.item.label);

describe("rankMatches", () => {
  it("one typed letter suggests the names starting with it, popular first", () => {
    expect(labels("r")).toEqual(["react", "redux"]);
  });
  it("prefers exact, then prefix, then alias, then word, then contains", () => {
    expect(labels("react")).toEqual(["react"]);
    expect(labels("js")[0]).toBe("javascript"); // alias typed in full beats names starting with it
    expect(labels("fico")).toEqual(["sap fico"]); // alias + word start
    expect(labels("script")).toEqual(["javascript"]); // contains
    expect(labels("odejs")).toEqual([]); // inside an alias is not a match
  });
  it("reports which alias matched", () => {
    expect(rankMatches("nodejs", ITEMS)[0].via).toBe("nodejs");
  });
  it("skips excluded items and returns nothing for blank input", () => {
    expect(labels("r", { skip: (it) => it.label === "react" })).toEqual(["redux"]);
    expect(labels("   ")).toEqual([]);
  });
  it("one letter does not match the middle of words", () => {
    expect(labels("y")).toEqual([]); // python has a y, but doesn't start with one
  });
  it("splitMatch bolds the typed part", () => {
    expect(splitMatch("javascript", "SCRIPT")).toEqual(["java", "script", ""]);
  });
});

function Skills({ initial = [], suggested = [] }) {
  const [skills, setSkills] = useState(initial);
  return (
    <>
      <SkillInput value={skills} onChange={setSkills} catalog={CATALOG} suggested={suggested} suggestedFor="Full Stack Developer" />
      <output data-testid="skills">{skills.join("|")}</output>
    </>
  );
}

describe("SkillInput dropdown", () => {
  it("suggests while typing and adds the clicked suggestion", async () => {
    const user = userEvent.setup();
    render(<Skills />);
    await user.type(screen.getByRole("combobox"), "re");
    expect(screen.getByRole("listbox")).toBeInTheDocument();
    const options = screen.getAllByRole("option").map((o) => o.textContent);
    expect(options.slice(0, 2)).toEqual(["react", "redux"]);
    await user.click(screen.getByRole("option", { name: /^redux/ }));
    expect(screen.getByTestId("skills")).toHaveTextContent("redux");
  });

  it("Enter takes the highlighted suggestion, arrows move it", async () => {
    const user = userEvent.setup();
    render(<Skills />);
    await user.type(screen.getByRole("combobox"), "r{ArrowDown}{Enter}");
    expect(screen.getByTestId("skills")).toHaveTextContent(/^redux$/);
  });

  it("an alias is saved under the canonical name", async () => {
    const user = userEvent.setup();
    render(<Skills />);
    await user.type(screen.getByRole("combobox"), "reactjs{Enter}");
    expect(screen.getByTestId("skills")).toHaveTextContent(/^react$/);
  });

  it("lets you type a skill that is not in the list", async () => {
    const user = userEvent.setup();
    render(<Skills />);
    await user.type(screen.getByRole("combobox"), "sap grc zzz");
    expect(screen.getByRole("option", { name: /Add “sap grc zzz” as typed/ })).toBeInTheDocument();
    await user.keyboard("{Enter}");
    expect(screen.getByTestId("skills")).toHaveTextContent(/^sap grc zzz$/);
  });

  it("does not offer skills that are already added", async () => {
    const user = userEvent.setup();
    render(<Skills initial={["react"]} />);
    await user.type(screen.getByRole("combobox"), "re");
    expect(screen.queryByRole("option", { name: /^react/ })).not.toBeInTheDocument();
  });

  it("Escape closes the list; comma adds what you typed", async () => {
    const user = userEvent.setup();
    render(<Skills />);
    await user.type(screen.getByRole("combobox"), "py{Escape}");
    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
    await user.type(screen.getByRole("combobox"), "thon,");
    expect(screen.getByTestId("skills")).toHaveTextContent(/^python$/);
  });

  it("offers a role's usual skills and adds them all in one click", async () => {
    const user = userEvent.setup();
    render(<Skills initial={["react"]} suggested={["react", "python", "node.js"]} />);
    expect(screen.getByText("Usually asked for Full Stack Developer")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^react$/ })).not.toBeInTheDocument(); // already have it
    await user.click(screen.getByRole("button", { name: "Add all" }));
    expect(screen.getByTestId("skills")).toHaveTextContent("react|python|node.js");
  });
});

const ROLES = [
  { role: "Full Stack Developer", category: "Software Development", skills: ["react"], aliases: ["fullstack developer"] },
  { role: "DevOps Engineer", category: "Cloud & DevOps", skills: ["docker"], aliases: [] },
  { role: "SAP FICO Consultant", category: "SAP", skills: ["sap fico"], aliases: [] },
];

function Role() {
  const [role, setRole] = useState("");
  return (
    <>
      <RoleInput id="role" value={role} onChange={setRole} roles={ROLES} aria-label="Role" />
      <output data-testid="role">{role}</output>
    </>
  );
}

describe("RoleInput dropdown", () => {
  it("lists common roles on focus and filters as you type", async () => {
    const user = userEvent.setup();
    render(<Role />);
    await user.click(screen.getByRole("combobox"));
    expect(screen.getAllByRole("option")).toHaveLength(3);
    await user.type(screen.getByRole("combobox"), "sap");
    expect(screen.getAllByRole("option").map((o) => o.textContent)).toEqual(["SAP FICO ConsultantSAP"]);
    await user.click(screen.getByRole("option"));
    expect(screen.getByTestId("role")).toHaveTextContent("SAP FICO Consultant");
  });

  it("finds roles by alias and still allows any custom role", async () => {
    const user = userEvent.setup();
    render(<Role />);
    await user.type(screen.getByRole("combobox"), "fullstack");
    expect(screen.getByRole("option", { name: /Full Stack Developer/ })).toBeInTheDocument();
    await user.clear(screen.getByRole("combobox"));
    await user.type(screen.getByRole("combobox"), "Quantum Gardener{Enter}");
    expect(screen.getByTestId("role")).toHaveTextContent("Quantum Gardener");
  });
});
