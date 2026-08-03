import type { APIRoute } from "astro";

export const POST: APIRoute = async ({ request }) => {
  try {
    const data = await request.json();
    const email = data.email?.trim();

    if (!email || !email.includes("@")) {
      return new Response(
        JSON.stringify({ error: "Please enter a valid email address." }),
        { status: 400, headers: { "Content-Type": "application/json" } }
      );
    }

    const LOOPS_API_KEY = import.meta.env.LOOPS_API_KEY || process.env.LOOPS_API_KEY;

    if (LOOPS_API_KEY) {
      try {
        await fetch("https://app.loops.so/api/v1/contacts/create", {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${LOOPS_API_KEY}`,
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            email,
            source: "Agewell Brief Homepage & Lead Magnet",
            userGroup: "Agewell Subscribers",
            subscribed: true
          })
        });
      } catch (err) {
        console.error("Loops API contact sync warning:", err);
      }
    }

    return new Response(
      JSON.stringify({
        success: true,
        message: "Welcome to Agewell Brief! Your 6 Biophysics Field Guides are ready for instant download.",
        guides: [
          { name: "Living Waters (Transport)", url: "/downloads/field-guides/living-waters-field-guide.pdf" },
          { name: "Inner Garden (Gut Ecology)", url: "/downloads/field-guides/inner-garden-field-guide.pdf" },
          { name: "Cell Shedding (Senescence)", url: "/downloads/field-guides/cell-shedding-field-guide.pdf" },
          { name: "Higher Flame (Metabolism)", url: "/downloads/field-guides/higher-flame-field-guide.pdf" },
          { name: "Luminous Mind (Cognition)", url: "/downloads/field-guides/luminous-mind-field-guide.pdf" },
          { name: "Dark Mirror (Mineral Balance)", url: "/downloads/field-guides/dark-mirror-field-guide.pdf" }
        ]
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    );
  } catch (error) {
    return new Response(
      JSON.stringify({ error: "Failed to process subscription." }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
};
