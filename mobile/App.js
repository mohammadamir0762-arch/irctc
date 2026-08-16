import { useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { API_BASE } from "./config";

function confidenceColor(probability) {
  if (probability >= 0.75) return "#34d399";
  if (probability >= 0.4) return "#fbbf24";
  return "#f87171";
}

export default function App() {
  const [pnrNumber, setPnrNumber] = useState("");
  const [loading, setLoading] = useState(false);
  const [waking, setWaking] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  async function checkPnr() {
    if (!/^\d{10}$/.test(pnrNumber)) {
      setError("PNR number must be exactly 10 digits.");
      return;
    }
    setError(null);
    setResult(null);
    setLoading(true);
    // Free hosting sleeps when idle and can take ~a minute to wake. Say so
    // instead of leaving a spinner with no explanation.
    const wakeTimer = setTimeout(() => setWaking(true), 3000);
    try {
      const res = await fetch(`${API_BASE}/pnr/${pnrNumber}`);
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || `Request failed (${res.status})`);
      }
      setResult(data);
    } catch (e) {
      setError(
        e.message === "Network request failed"
          ? `Could not reach the API at ${API_BASE}. Check your internet connection — some networks block this host.`
          : e.message
      );
    } finally {
      clearTimeout(wakeTimer);
      setWaking(false);
      setLoading(false);
    }
  }

  return (
    <ScrollView contentContainerStyle={styles.container}>
      <StatusBar barStyle="light-content" />
      <Text style={styles.title}>PNR Confirmation Predictor</Text>
      <Text style={styles.subtitle}>
        Enter your 10-digit PNR to check its status and confirmation probability.
      </Text>

      <View style={styles.inputRow}>
        <TextInput
          style={styles.input}
          value={pnrNumber}
          onChangeText={setPnrNumber}
          placeholder="e.g. 1234567890"
          placeholderTextColor="#64748b"
          keyboardType="number-pad"
          maxLength={10}
        />
        <Pressable style={styles.button} onPress={checkPnr} disabled={loading}>
          {loading ? (
            <ActivityIndicator color="#0f172a" />
          ) : (
            <Text style={styles.buttonText}>Check</Text>
          )}
        </Pressable>
      </View>

      {waking && (
        <Text style={styles.waking}>
          Waking up the server (free hosting sleeps when idle) — up to a minute...
        </Text>
      )}

      {error && <Text style={styles.error}>{error}</Text>}

      {result?.is_mock && (
        <Text style={styles.mockBanner}>
          No real PNR provider is configured yet — showing simulated data for demo purposes only.
        </Text>
      )}

      {result?.resolved && (
        <View
          style={[
            styles.resolvedCard,
            { backgroundColor: result.status === "Confirmed" ? "#34d39926" : "#f8717126" },
          ]}
        >
          <Text
            style={[
              styles.resolvedText,
              { color: result.status === "Confirmed" ? "#34d399" : "#f87171" },
            ]}
          >
            PNR {result.pnr_number}: {result.status}
          </Text>
        </View>
      )}

      {result && !result.resolved && (
        <>
          <View style={styles.summaryCard}>
            <Text style={styles.trainTitle}>
              {result.pnr_summary.train_name} ({result.pnr_summary.train_number})
            </Text>
            <Text style={styles.muted}>
              {result.pnr_summary.from_station} → {result.pnr_summary.to_station}
            </Text>
            <Text style={styles.muted}>
              Journey date: {result.pnr_summary.journey_date} · Chart prepared:{" "}
              {result.pnr_summary.chart_prepared ? "Yes" : "No"}
            </Text>
            <Text style={styles.muted}>Status: {result.pnr_summary.current_status}</Text>
          </View>

          <View style={styles.resultCard}>
            <View
              style={[styles.probabilityRing, { borderColor: confidenceColor(result.probability) }]}
            >
              <Text style={styles.probabilityValue}>
                {Math.round(result.probability * 100)}%
              </Text>
            </View>
            <Text style={styles.confidenceLabel}>{result.confidence_label}</Text>

            {result.top_factors.map((f, i) => (
              <View key={i} style={styles.factorRow}>
                <Text style={styles.factorText}>
                  <Text style={styles.factorName}>{f.factor}: </Text>
                  {f.impact}
                </Text>
              </View>
            ))}

            {result.estimated_fields?.length > 0 && (
              <Text style={styles.estimatedNote}>
                Some inputs ({result.estimated_fields.join(", ")}) aren't available from the PNR
                lookup and are estimated, not exact.
              </Text>
            )}
          </View>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flexGrow: 1,
    backgroundColor: "#0f172a",
    padding: 24,
    paddingTop: 64,
  },
  title: {
    color: "#e2e8f0",
    fontSize: 24,
    fontWeight: "700",
    marginBottom: 4,
  },
  subtitle: {
    color: "#94a3b8",
    fontSize: 14,
    marginBottom: 24,
  },
  inputRow: {
    flexDirection: "row",
    gap: 8,
  },
  input: {
    flex: 1,
    backgroundColor: "#1e293b",
    borderWidth: 1,
    borderColor: "#334155",
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    color: "#e2e8f0",
    fontSize: 16,
    letterSpacing: 1,
  },
  button: {
    backgroundColor: "#38bdf8",
    borderRadius: 10,
    paddingHorizontal: 20,
    justifyContent: "center",
    alignItems: "center",
    minWidth: 84,
  },
  buttonText: {
    color: "#0f172a",
    fontWeight: "700",
    fontSize: 15,
  },
  error: {
    color: "#f87171",
    marginTop: 12,
    fontSize: 13,
  },
  waking: {
    color: "#38bdf8",
    marginTop: 12,
    fontSize: 13,
  },
  mockBanner: {
    marginTop: 12,
    padding: 10,
    backgroundColor: "#fbbf241f",
    borderWidth: 1,
    borderColor: "#fbbf2459",
    borderRadius: 8,
    color: "#fbbf24",
    fontSize: 12,
  },
  resolvedCard: {
    marginTop: 20,
    padding: 20,
    borderRadius: 10,
    alignItems: "center",
  },
  resolvedText: {
    fontWeight: "700",
    fontSize: 16,
  },
  summaryCard: {
    marginTop: 20,
    backgroundColor: "#1e293b",
    borderWidth: 1,
    borderColor: "#334155",
    borderRadius: 10,
    padding: 14,
  },
  trainTitle: {
    color: "#e2e8f0",
    fontWeight: "700",
    fontSize: 15,
    marginBottom: 4,
  },
  muted: {
    color: "#94a3b8",
    fontSize: 13,
    lineHeight: 20,
  },
  resultCard: {
    marginTop: 16,
    alignItems: "center",
    backgroundColor: "#1e293b",
    borderRadius: 16,
    padding: 24,
  },
  probabilityRing: {
    width: 110,
    height: 110,
    borderRadius: 55,
    borderWidth: 6,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 10,
  },
  probabilityValue: {
    color: "#e2e8f0",
    fontSize: 24,
    fontWeight: "700",
  },
  confidenceLabel: {
    color: "#e2e8f0",
    fontWeight: "600",
    fontSize: 15,
    marginBottom: 14,
  },
  factorRow: {
    backgroundColor: "#0f172a",
    borderWidth: 1,
    borderColor: "#334155",
    borderRadius: 8,
    padding: 10,
    marginBottom: 8,
    width: "100%",
  },
  factorText: {
    color: "#e2e8f0",
    fontSize: 13,
  },
  factorName: {
    color: "#38bdf8",
    fontWeight: "700",
  },
  estimatedNote: {
    color: "#94a3b8",
    fontSize: 11,
    marginTop: 6,
    textAlign: "center",
  },
});
