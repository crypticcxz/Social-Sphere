import { chromium } from "playwright";

async function run(searchTerm = "Harvard professor") {
  const browser = await chromium.launch({
    headless: false, // keep visible for debugging
    slowMo: 100      // small delay for stability
  });

  const page = await browser.newPage();

  // Step 1: Go to Google Scholar homepage
  await page.goto("https://scholar.google.com/");

  // Step 2: Enter search term into the search box and press Enter
  await page.fill("input[name='q']", searchTerm);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(2000);

  // Step 3: Open the hamburger menu properly
  await page.waitForSelector("#gs_hdr_mnu", { state: "visible" });
  await page.click("#gs_hdr_mnu", { force: true });
  await page.waitForSelector("div#gs_hdr_drw", { state: "visible" });

  // Step 4: Click "Profiles" inside the drawer
//   await page.getByRole("link", { name: "Profiles" }).click();
await page.getByText("Profiles").click();
  await page.waitForTimeout(3000);

  // Step 5: Scrape professor profile links
  const professors = await page.$$("a.gs_ai_name");

  for (let i = 0; i < professors.length; i++) {
    const prof = professors[i];
    const name = await prof.innerText();
    await prof.click();
    await page.waitForTimeout(2000);

    try {
      // Extract h-index and citations
      const hIndexText = await page.innerText("td.gsc_rsb_std:nth-child(2)");
      const citationsText = await page.innerText("td.gsc_rsb_std:nth-child(1)");

      const hIndex = parseInt(hIndexText, 10);
      const citations = parseInt(citationsText, 10);

      if (citations > 5000 && hIndex > 40) {
        console.log(`✅ Qualified: ${name}, h-index=${hIndex}, citations=${citations}`);
      } else {
        console.log(`❌ Not qualified: ${name}, h-index=${hIndex}, citations=${citations}`);
      }
    } catch (e) {
      console.log(`⚠️ Error processing ${name}: ${e}`);
    }

    // Go back to profiles list
    await page.goBack();
    await page.waitForTimeout(2000);
  }

  await browser.close();
}

run();
