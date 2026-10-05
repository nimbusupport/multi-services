document.addEventListener("DOMContentLoaded", () => {
  const slides = Array.from(document.querySelectorAll(".carousel-slide"));
  const dots = Array.from(document.querySelectorAll(".carousel-dots button"));
  const passwordInput = document.getElementById("password");
  const passwordToggle = document.querySelector(".password-toggle");
  const helperButtons = Array.from(document.querySelectorAll(".helper-toggle-btn"));
  const helperPanels = Array.from(document.querySelectorAll(".helper-panel"));
  const registrationForm = document.getElementById("registration-request-form");
  const forgotForm = document.getElementById("forgot-password-form");
  const forgotEmailInput = document.getElementById("forgot-email");
  const forgotFields = document.getElementById("forgot-password-fields");
  const forgotCheckButton = document.getElementById("forgot-check-btn");
  const registrationMessage = document.getElementById("registration-message");
  const forgotMessage = document.getElementById("forgot-message");
  const loginHelperStatus = document.getElementById("login-helper-status");
  let activeIndex = 0;
  let timer = null;

  function setHelperMessage(element, message, tone = "") {
    if (!element) return;
    element.textContent = message || "";
    element.classList.remove("success", "error");
    if (tone) element.classList.add(tone);
  }

  async function postJson(url, payload) {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) {
      throw new Error(data.message || "Request failed");
    }
    return data;
  }

  function showSlide(index) {
    activeIndex = (index + slides.length) % slides.length;
    slides.forEach((slide, slideIndex) => {
      slide.classList.toggle("active", slideIndex === activeIndex);
    });
    dots.forEach((dot, dotIndex) => {
      dot.classList.toggle("active", dotIndex === activeIndex);
    });
  }

  function startCarousel() {
    if (timer) clearInterval(timer);
    timer = setInterval(() => showSlide(activeIndex + 1), 4000);
  }

  dots.forEach((dot) => {
    dot.addEventListener("click", () => {
      showSlide(Number(dot.dataset.slide || 0));
      startCarousel();
    });
  });

  if (passwordInput && passwordToggle) {
    passwordToggle.addEventListener("click", () => {
      const showing = passwordInput.type === "text";
      passwordInput.type = showing ? "password" : "text";
      passwordToggle.classList.toggle("showing", !showing);
      passwordToggle.setAttribute("aria-pressed", String(!showing));
      passwordToggle.setAttribute("aria-label", showing ? "Show password" : "Hide password");
    });
  }

  helperButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const targetId = button.dataset.helperTarget;
      const targetPanel = document.getElementById(targetId);
      if (!targetPanel) return;

      const shouldOpen = targetPanel.hidden;
      helperPanels.forEach((panel) => {
        panel.hidden = true;
      });
      helperButtons.forEach((item) => item.classList.remove("active"));

      if (shouldOpen) {
        targetPanel.hidden = false;
        button.classList.add("active");
      }
    });
  });

  registrationForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(registrationForm);
    const payload = {
      email: String(formData.get("email") || "").trim(),
      full_name: String(formData.get("full_name") || "").trim(),
      organization: String(formData.get("organization") || "").trim(),
    };

    setHelperMessage(registrationMessage, "");

    try {
      const data = await postJson("/login/request-registration", payload);
      registrationForm.reset();
      setHelperMessage(registrationMessage, "", "");
      helperPanels.forEach((panel) => {
        panel.hidden = true;
      });
      helperButtons.forEach((item) => item.classList.remove("active"));
      setHelperMessage(loginHelperStatus, data.message || "Registration request delivered", "success");
    } catch (error) {
      setHelperMessage(loginHelperStatus, "", "");
      setHelperMessage(registrationMessage, error.message || "Failed to send registration request", "error");
    }
  });

  forgotCheckButton?.addEventListener("click", async () => {
    const email = String(forgotEmailInput?.value || "").trim();
    setHelperMessage(forgotMessage, "");
    if (forgotFields) {
      forgotFields.hidden = true;
    }

    try {
      const data = await postJson("/login/forgot-password/check", { email });
      if (forgotFields) {
        forgotFields.hidden = false;
      }
      setHelperMessage(forgotMessage, data.message || "Email found", "success");
      document.getElementById("forgot-password-new")?.focus();
    } catch (error) {
      setHelperMessage(forgotMessage, error.message || "Email check failed", "error");
    }
  });

  forgotForm?.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(forgotForm);
    const payload = {
      email: String(formData.get("email") || "").trim(),
      password: String(formData.get("password") || ""),
      confirm_password: String(formData.get("confirm_password") || ""),
    };

    setHelperMessage(forgotMessage, "");

    try {
      const data = await postJson("/login/forgot-password/reset", payload);
      forgotForm.reset();
      if (forgotFields) {
        forgotFields.hidden = true;
      }
      setHelperMessage(forgotMessage, data.message || "Password updated successfully", "success");
    } catch (error) {
      setHelperMessage(forgotMessage, error.message || "Password reset failed", "error");
    }
  });

  if (slides.length > 1) startCarousel();
});




