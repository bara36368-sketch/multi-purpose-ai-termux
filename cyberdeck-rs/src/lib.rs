//! cyberdeck-rs: PyO3 fast path for the cyberdeck orchestrator.
//!
//! Owns the pure-logic cores of the task/sessions/fleet features so the CLI
//! does no string scanning or state-diffing in Python:
//!
//!   * `classify_intent`  — keyword dispatch over the INTENTS table
//!   * `has_placeholders` — refuse template commands with "topic" / <...>
//!   * `next_id`          — monotonic session ids
//!   * `tail`             — safe last-N-chars truncation for output_tail
//!   * `fleet_alerts`     — up/down flips + model swaps between polls
//!
//! cyberdeck.py uses these only when the extension is importable
//! (`_HAS_RS`); it falls back to its own pure-Python implementations
//! otherwise, so the CLI never hard-depends on a build.

use std::collections::HashMap;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

/// First intent whose keyword table matches the prompt (case-insensitive).
/// `intents` is the INTENTS structure: list of (name, keywords, module, command).
#[pyfunction]
fn classify_intent(
    prompt: &str,
    intents: Vec<(String, Vec<String>, String, String)>,
) -> PyResult<Option<(String, String, String)>> {
    let text = prompt.to_lowercase();
    for (name, keywords, module, command) in intents {
        if keywords.iter().any(|k| text.contains(&k.to_lowercase())) {
            return Ok(Some((name, module, command)));
        }
    }
    Ok(None)
}

/// Template commands embed placeholders as "topic" or <...> — neither is
/// safe to execute verbatim.
#[pyfunction]
fn has_placeholders(command: &str) -> bool {
    command.contains('"') || command.contains('<') || command.contains('>')
}

/// Next monotonic session id: last id + 1, or 1 for an empty journal.
#[pyfunction]
fn next_id(sessions: Vec<Bound<'_, PyDict>>) -> PyResult<u64> {
    match sessions.last() {
        Some(last) => {
            let id: u64 = last
                .get_item("id")?
                .ok_or_else(|| PyValueError::new_err("session missing 'id'"))?
                .extract()?;
            Ok(id + 1)
        }
        None => Ok(1),
    }
}

/// Last `max_chars` characters (char-boundary safe, no mid-glyph splits).
#[pyfunction]
fn tail(text: &str, max_chars: usize) -> String {
    let chars: Vec<char> = text.chars().collect();
    if chars.len() <= max_chars {
        text.to_string()
    } else {
        chars[chars.len() - max_chars..].iter().collect()
    }
}

fn str_field(d: &Bound<'_, PyDict>, key: &str) -> Option<String> {
    let v = d.get_item(key).ok().flatten()?;
    v.extract::<String>().ok()
}

fn name_status_model(d: &Bound<'_, PyDict>) -> PyResult<(String, String, Option<String>)> {
    let name = d
        .get_item("name")?
        .ok_or_else(|| PyValueError::new_err("phone entry missing 'name'"))?
        .extract::<String>()?;
    let status = str_field(d, "status").unwrap_or_default();
    let model = str_field(d, "model").or_else(|| str_field(d, "active_model"));
    Ok((name, status, model))
}

/// State-change lines between two fleet snapshots: up/down flips and model
/// swaps (the OOM-ladder step-down detector). Mirrors the Python reference.
#[pyfunction]
fn fleet_alerts(prev: &Bound<'_, PyAny>, cur: &Bound<'_, PyAny>) -> PyResult<Vec<String>> {
    let mut seen: HashMap<String, (String, Option<String>)> = HashMap::new();
    for item in prev.try_iter()? {
        let item = item?;
        let d = item.downcast::<PyDict>()?;
        let (name, status, model) = name_status_model(d)?;
        seen.insert(name, (status, model));
    }
    let mut out = Vec::new();
    for item in cur.try_iter()? {
        let item = item?;
        let d = item.downcast::<PyDict>()?;
        let (name, status, model) = name_status_model(d)?;
        if let Some((old_status, old_model)) = seen.get(&name) {
            if *old_status != status {
                out.push(format!("ALERT {}: {} -> {}", name, old_status, status));
            } else if status == "UP" {
                if let (Some(om), Some(nm)) = (old_model, &model) {
                    if *om != *nm {
                        out.push(format!("ALERT {}: model swapped {} -> {}", name, om, nm));
                    }
                }
            }
        }
    }
    Ok(out)
}

#[pymodule]
fn cyberdeck_rs(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(classify_intent, m)?)?;
    m.add_function(wrap_pyfunction!(has_placeholders, m)?)?;
    m.add_function(wrap_pyfunction!(next_id, m)?)?;
    m.add_function(wrap_pyfunction!(tail, m)?)?;
    m.add_function(wrap_pyfunction!(fleet_alerts, m)?)?;
    Ok(())
}
