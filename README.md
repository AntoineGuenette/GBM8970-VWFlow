# GBM8970-VWFlow

von Willebrand factor (VWF) is a multimeric glycoprotein essential to primary hemostasis. Under high shear forces—such as those generated during vascular injury—VWF unravels and exposes its A1 domains, enabling platelet binding through GPIb receptors. This mechanism, known as shear-induced platelet aggregation (SIPA), initiates platelet aggregation and clot formation.

However, current clinical tests measure VWF activity under static conditions, which do not reproduce the physiological shear required for proper VWF activation. This limitation can reduce diagnostic accuracy.

This project aims to design a microfluidic device capable of measuring VWF activity under dynamic shear conditions, providing a more faithful representation of SIPA. The device receives a small volume of platelet-poor plasma (PPP) mixed with lyophilized platelets or latex beads coated with platelet receptors, applies controlled shear via magnetic agitation, and quantifies aggregation optically. The software in this repository then converts the aggregation signal into a semi-automated estimate of VWF activity.

This repository contains:
- firmware for the microcontroller controlling magnetic agitation and shear generation;
- data processing code converting optical aggregation signals into VWF activity measurements;
- Python scripts for simulations, modeling, and analysis.
