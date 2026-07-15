const API_URL = `${import.meta.env.VITE_API_URL}/query`;

export async function askQuery(question) {
  const response = await fetch(API_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ question }),
  });

  const data = await response.json();

  if (!response.ok || data.error) {
    throw new Error(data.error || "Something went wrong.");
  }

  return data;
}