// Test harness for src/AIBody/IdleMovement.cs (version 60): the plugin's real file compiled outside VaM.
// stdin: one JSON object {"cmd": ..., ...}; stdout: one JSON line.
using System;
using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Nodes;
using AIBody;

static class Program
{
    static List<IdlePart> Parts(JsonNode n)
    {
        var list = new List<IdlePart>();
        if (n == null) return list;
        foreach (var p in n.AsArray())
        {
            float F(string k) => p[k] == null ? 0f : p[k].GetValue<float>();
            list.Add(new IdlePart(p["c"].GetValue<string>(), p["a"]?.GetValue<string>() ?? IdleMovementPlan.AnchorOf(p["c"].GetValue<string>()),
                F("px"), F("py"), F("pz"), F("rx"), F("ry"), F("rz")));
        }
        return list;
    }

    static JsonObject Part(IdlePart p) => new JsonObject
    {
        ["c"] = p.Control, ["a"] = p.Anchor, ["px"] = p.PX, ["py"] = p.PY, ["pz"] = p.PZ, ["rx"] = p.RX, ["ry"] = p.RY, ["rz"] = p.RZ
    };

    static int Main()
    {
        var c = JsonNode.Parse(Console.In.ReadLine());
        string cmd = c["cmd"].GetValue<string>();
        JsonNode result;
        switch (cmd)
        {
            case "constants":
                var l = new JsonArray();
                foreach (float v in new[] { 0f, 0.5f, 1f, -3f, 7f })
                    l.Add(new JsonObject { ["l"] = v, ["amp"] = IdleMovementPlan.Amplitude(v), ["wmin"] = IdleMovementPlan.WaitMin(v),
                        ["wmax"] = IdleMovementPlan.WaitMax(v), ["slow"] = IdleMovementPlan.Slowness(v) });
                var controls = new JsonArray();
                foreach (var s in IdleMovementPlan.Controls) controls.Add(s + "@" + IdleMovementPlan.AnchorOf(s));
                result = new JsonObject { ["levels"] = l, ["controls"] = controls, ["label"] = IdleMovementPlan.PoserLabel,
                    ["cslist"] = IdleMovementPlan.PoserCslist, ["suffix"] = IdleMovementPlan.PoserStorableSuffix,
                    ["default"] = IdleMovementPlan.DefaultLiveliness };
                break;
            case "standing":
                result = IdleMovementPlan.IsStanding(Parts(c["parts"]));
                break;
            case "jump":
                result = IdleMovementPlan.IsJump(c["m"].GetValue<float>(), c["dt"].GetValue<float>());
                break;
            case "shifted":
                var outp = new JsonArray();
                foreach (var p in Parts(c["parts"])) outp.Add(Part(IdleMovementPlan.Shifted(p, c["side"].GetValue<int>(), c["a"].GetValue<float>())));
                result = outp;
                break;
            case "build":
                string json = IdleMovementPlan.BuildJson(c["uid"].GetValue<string>(), Parts(c["parts"]), c["l"].GetValue<float>());
                result = json == null ? null : JsonValue.Create(json);
                break;
            case "gate":
                var g = new IdleMovementGate();
                var steps = new JsonArray();
                foreach (var s in c["steps"].AsArray())
                {
                    if (s["enabled"] != null) g.Enabled = s["enabled"].GetValue<bool>();
                    if (s["lively"] != null) g.Liveliness = s["lively"].GetValue<float>();
                    if (s["stopNow"] != null) { g.StopNow(s["stopNow"].GetValue<string>()); steps.Add("StopNow|" + g.Running + "|" + g.Status); continue; }
                    bool B(string k, bool d) => s[k] == null ? d : s[k].GetValue<bool>();
                    var i = new IdleMovementInputs
                    {
                        Available = B("available", true), BodyControl = B("body", true), Cooldown = B("cooldown", false),
                        Settling = B("settling", false), Loading = B("loading", false), Outside = B("outside", false),
                        Standing = B("standing", true)
                    };
                    var step = g.Update(i);
                    steps.Add(step + "|" + g.Running + "|" + g.Status);
                }
                result = steps;
                break;
            default:
                Console.Error.WriteLine("unknown cmd " + cmd);
                return 2;
        }
        Console.WriteLine(result == null ? "null" : result.ToJsonString());
        return 0;
    }
}
