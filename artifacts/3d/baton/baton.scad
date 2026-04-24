
// --- MASTER CONFIGURATION ---


margin = 3;
pi_hole_h = 58;
pi_hole_w = 23;



dweii_x = margin+13;
dweii_hole_h = 37;
dweii_hole_w = 83;

dweii_z=22;

dweii_port_w = 16;
dweii_port_h = 8;


plate_w = dweii_x+dweii_hole_w+margin;
plate_h = margin*2 + pi_hole_h    ;
vault_z = dweii_z+10;       
wall_t = 2.5;       
lid_clearance = 0.5; 
lid_wall = 2.0;
lid_depth = wall_t*2;




pi_z = dweii_z + 5;

lid_x=wall_t + margin + pi_hole_w + margin*2;

encased_diameter = 56;

ext_r = 4; // 4mm radius gives a nice 'rugged' curve

// --- 1. THE MAIN BOX ---
difference() {
    
    // POSITIVE SPACE (Solid parts)
   // POSITIVE SPACE (Rounded Box)
hull() {
    // Top-Left
    translate([ext_r, ext_r, 0]) 
        cylinder(r=ext_r, h=vault_z + wall_t, $fn=50);
    // Top-Right
    translate([plate_w + (wall_t*2) - ext_r, ext_r, 0]) 
        cylinder(r=ext_r, h=vault_z + wall_t, $fn=50);
    // Bottom-Left
    translate([ext_r, plate_h + (wall_t*2) - ext_r, 0]) 
        cylinder(r=ext_r, h=vault_z + wall_t, $fn=50);
    // Bottom-Right
    translate([plate_w + (wall_t*2) - ext_r, plate_h + (wall_t*2) - ext_r, 0]) 
        cylinder(r=ext_r, h=vault_z + wall_t, $fn=50);
}


    // ---ARM STRAP SLOTS (Horizontal Alignment) ---
    // Spaced to run between the DWEII standoffs
    // Slot 1
    translate([dweii_x + wall_t + 10, (plate_h-dweii_hole_h)/2, -1])
    cube([plate_w - dweii_x - 22, 2.5, wall_t + 2]); 

    // Slot 2
    translate([dweii_x + wall_t + 10, plate_h -(plate_h-dweii_hole_h)/2, -1])
    cube([plate_w - dweii_x - 22, 2.5, wall_t + 2]);


    // NEGATIVE SPACE (The Drills)
    
    // Pi ports
    translate([-1, -1, pi_z+ wall_t-1]) // Move start slightly outside the x=0 plane
    cube([lid_x+1, plate_h + wall_t*2+2, vault_z - pi_z + 4]);
    
    
    
    // dweii port
    translate([plate_w, (plate_h+wall_t*2)/2 - dweii_port_w/2, wall_t+dweii_z-dweii_port_h/2])
    cube([16, dweii_port_w, dweii_port_h]);
    
   
    
    // Hollow out the center
    translate([wall_t, wall_t, wall_t]) 
    cube([plate_w, plate_h, vault_z + 10]); 
    
    

    // THE DUAL-WALL VENT GRID
    grid_scale_x=1/8;
    for(i = [6 : 12 : vault_z-6]) {
        for (v = [plate_w*grid_scale_x : plate_w*grid_scale_x : plate_w-plate_w*grid_scale_x]) { 
            // Wall 1 (Front)
            translate([v + wall_t, -5, i + wall_t]) 
            rotate([-90, 0, 0]) cylinder(h=20, d=4.5, $fn=6);
            
            // Wall 2 (Back)
            translate([v + wall_t, plate_h + wall_t - 5, i + wall_t]) 
            rotate([-90, 0, 0]) cylinder(h=20, d=4.5, $fn=6);
        }
    }
    
    
    //pi side vent
    // Wall 3 (Side Wall - Pi Side)
    // We only vent the area below the Pi ports to keep the structure strong
    grid2_scale_x=1/7;
    for(i = [6 : 6 : pi_z - 12]) { 
        for (v = [wall_t+plate_h*grid2_scale_x : plate_h*grid2_scale_x : plate_h-plate_h*grid2_scale_x+wall_t]) { 
          
        
            translate([plate_w+wall_t-5, v, i + wall_t]) 
            rotate([0, 90, 0]) cylinder(h=20, d=4.5, $fn=6);
        }
    }
    
    //for(i = [ : 12 : pi_z - 4]) { 
        for (v = [wall_t+plate_h*grid2_scale_x : plate_h*grid2_scale_x : plate_h-plate_h*grid2_scale_x+wall_t]) { 
            translate([-5, v, (pi_z)/2]) 
            rotate([0, 90, 0]) cylinder(h=20, d=4.5, $fn=6);
            
 
        }
    //}
    
    /*
    // Reduced Venting for UPS side (Back Wall)
    for(i = [6 : 12 : vault_z-6]) { // Increased vertical step to 12
        for (v = [dweii_x : 12 : plate_w]) { // Only vent starting at the UPS position
            translate([v + wall_t, plate_h + wall_t - 5, i + wall_t]) 
            rotate([-90, 0, 0]) cylinder(h=20, d=2, $fn=6);
        }
    }
    */
}

// --- STANDOFF MODULE ---
module standoff(x, y, h=23) {
    translate([x, y, 0]) 
    difference() {
        cylinder(h=h, d=6, $fn=50);   // 7mm total (Sitting on floor)
        translate([0,0,-1]) 
        cylinder(h=h+2, d=2.2, $fn=50); // M2.5 Self-tap hole
    }
}

// --- STANDOFFS (Now inside the union and translated correctly) ---
translate([wall_t, wall_t, wall_t]) {
    
    //pi
    standoff(margin, (plate_h - pi_hole_h)/2, pi_z);
    standoff(margin, (plate_h - pi_hole_h)/2 + pi_hole_h, pi_z);  
    standoff(margin+pi_hole_w, (plate_h - pi_hole_h)/2, pi_z);  
    standoff(margin+pi_hole_w, (plate_h - pi_hole_h)/2 + pi_hole_h, pi_z); 
    
    //dweii
    standoff(dweii_x, (plate_h - dweii_hole_h)/2, dweii_z); 
    standoff(dweii_x, (plate_h - dweii_hole_h)/2 + dweii_hole_h, dweii_z); 
    standoff(dweii_x+dweii_hole_w, (plate_h - dweii_hole_h)/2, dweii_z);  
    standoff(dweii_x+dweii_hole_w, (plate_h - dweii_hole_h)/2 + dweii_hole_h, dweii_z); 
    
    //lid
    standoff(lid_x + margin + 2-wall_t, margin+2, vault_z-wall_t);
    standoff(lid_x + margin + 2-wall_t, plate_h-margin-2, vault_z-wall_t);
    standoff(plate_w-margin-2, margin+2, vault_z-wall_t);
    standoff(plate_w-margin-2, plate_h-margin-2, vault_z-wall_t);
   
}
        

// --- 2. THE LID ---
translate([0, plate_h + 40, 0]) 
difference() {
    
    // POSITIVE SPACE (Rounded Right Side, Sharp Left Side)
    hull() {
        // Left-Top (Sharp corner at lid_x)
        translate([lid_x, 0, 0]) 
            cylinder(r=0.1, h=lid_depth, $fn=4);
        
        // Left-Bottom (Sharp corner at lid_x)
        translate([lid_x, plate_h + (wall_t*2), 0]) 
            cylinder(r=0.1, h=lid_depth, $fn=4);
            
        // Right-Top (Rounded to match box)
        translate([plate_w + (wall_t*2) - ext_r, ext_r, 0]) 
            cylinder(r=ext_r, h=lid_depth, $fn=50);
            
        // Right-Bottom (Rounded to match box)
        translate([plate_w + (wall_t*2) - ext_r, plate_h + (wall_t*2) - ext_r, 0]) 
            cylinder(r=ext_r, h=lid_depth, $fn=50);
    }

    // encased magnet
    translate([lid_x + wall_t + encased_diameter/2, (plate_h + wall_t*2)/2, -1])
    cylinder(h=wall_t+1, d=encased_diameter, $fn=50);

     // dweii charge leds
    translate([dweii_x+dweii_hole_w-7, (plate_h - dweii_hole_h)/2 + 5, -1])
    cube([3,3,wall_t*2+2]);
    
    // holes
    translate([lid_x + margin+2, margin+wall_t+2,-1])
    cylinder(h=lid_depth+10, d=2.9, $fn=50); 
    
    translate([lid_x + margin+2, plate_h+wall_t-margin-2,-1])
    cylinder(h=lid_depth+10, d=2.9, $fn=50); 
    
    translate([wall_t+plate_w-margin-2, margin+wall_t+2,-1])
    cylinder(h=lid_depth+10, d=2.9, $fn=50); 
    
    translate([wall_t+plate_w-margin-2, plate_h+wall_t-margin-2,-1])
    cylinder(h=lid_depth+10, d=2.9, $fn=50); 
    

    // lip
    
    translate([lid_x-1,-1,wall_t])
    cube([plate_w - lid_x +2 + (wall_t*2), 
          wall_t+1 + lid_clearance, 
          wall_t+10]);
 
    translate([lid_x-1,plate_h+wall_t-lid_clearance,wall_t])
    cube([plate_w - lid_x  +2 + (wall_t*2), 
          wall_t + lid_clearance+1, 
          wall_t+10]);

    translate([plate_w+wall_t-lid_clearance,-1,wall_t])
    cube([wall_t + lid_clearance+1, 
          plate_h + (wall_t*2)+2, 
          wall_t+10]);
}




