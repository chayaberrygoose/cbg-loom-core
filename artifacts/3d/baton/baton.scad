
// --- MASTER CONFIGURATION ---



margin = 2.9;
pi_hole_h = 58;
pi_hole_w = 23;


dweii_x = margin;
dweii_hole_h = 37;
dweii_hole_w = 83;

dweii_z=12;
pi_z = dweii_z + 24;
vault_z = pi_z+2;

usbc_w = 13;
usbc_h = 6;



plate_w = dweii_x+dweii_hole_w+margin;
plate_h = margin*2 + pi_hole_h    ;
     
wall_t = 2.9;       
lid_clearance = 0.5; 
lid_wall = 2.0;
lid_depth = wall_t*1.5;



pi_port_y=margin+wall_t;



lid_x=wall_t+pi_hole_w+margin*2;

bayite_hole_w = 23;
bayite_hole_h = 14.5;

ext_r = 6; // 4mm radius gives a nice 'rugged' curve

// --- 1. THE MAIN BOX ---
difference() {
    
    // POSITIVE SPACE (Main Chassis + Integrated Wings)
    union() {
        // --- THE MAIN ROUNDED BOX ---
        hull() {
            translate([ext_r, ext_r, 0]) cylinder(r=ext_r, h=vault_z + wall_t, $fn=50);
            translate([plate_w + (wall_t*2) - ext_r, ext_r, 0]) cylinder(r=ext_r, h=vault_z + wall_t, $fn=50);
            translate([ext_r, plate_h + (wall_t*2) - ext_r, 0]) cylinder(r=ext_r, h=vault_z + wall_t, $fn=50);
            translate([plate_w + (wall_t*2) - ext_r, plate_h + (wall_t*2) - ext_r, 0]) cylinder(r=ext_r, h=vault_z + wall_t, $fn=50);
        }

       // --- THE OPTIMIZED SYMMETRIC STRAP WINGS ---
        wing_w = 10; // Shorter X for less leverage
        wing_h = 56; 
        wing_z = 4.0; // Thicker Z for rigidity
        
        for(side = [0, 1]) { 
            translate([side * (plate_w + wall_t*2), (plate_h + wall_t*2)/2 - wing_h/2, 0])
            difference() {
                hull() {
                    // Attachment side - now slightly taller to "grip" the wall
                    translate([side == 0 ? 0 : -2, 2, 0]) cube([2, wing_h-4, wing_z + 2]); 
                    // Outer side
                    translate([side == 0 ? -wing_w + 3 : wing_w - 3, 3, 0]) cylinder(r=3, h=wing_z, $fn=30);
                    translate([side == 0 ? -wing_w + 3 : wing_w - 3, wing_h - 3, 0]) cylinder(r=3, h=wing_z, $fn=30);
                }
                
                // The Strap Slot
                translate([side == 0 ? -wing_w + 3 : wing_w - 6.5, (wing_h - 52)/2, -1]) 
                    cube([3.5, 52, wing_z + 10]);
            }
        }
    }
    


    // NEGATIVE SPACE (The Drills)
    
    

    // Hollow out center
    translate([wall_t, wall_t, wall_t]) {
        hull() {
            // Internal Top-Left
            translate([ext_r-wall_t, ext_r-wall_t, 0]) 
                cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
            // Internal Top-Right
            translate([plate_w - (ext_r-wall_t), ext_r-wall_t, 0]) 
                cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
            // Internal Bottom-Left
            translate([ext_r-wall_t, plate_h - (ext_r-wall_t), 0]) 
                cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
            // Internal Bottom-Right
            translate([plate_w - (ext_r-wall_t), plate_h - (ext_r-wall_t), 0]) 
                cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
        }
    }
    
    // pi sides
    translate([wall_t+margin, -1, pi_z+ wall_t-1]) // Move start slightly outside the x=0 plane
    cube([lid_x-(wall_t+margin), plate_h + wall_t*2+2, vault_z - pi_z + 4]);

    // pi front
    translate([-1, wall_t+margin, wall_t+pi_z-usbc_h/2+1+3/2]) // Move start slightly outside the x=0 plane
    cube([16, pi_hole_h, 20]);

    // dweii port
    translate([-1, (plate_h+wall_t*2)/2 - usbc_w/2, wall_t+dweii_z-usbc_h/2-1-3/2])
    cube([16, usbc_w, usbc_h]);
    
    // button
    button_d = 13.5;
    translate([margin+pi_hole_w/2 + wall_t, plate_h-1, (wall_t*2+pi_z)/2]) 
    rotate([-90, 0, 0]) cylinder(h=20, d=button_d, $fn=50);
   
    

    
    // THE DUAL-WALL VENT GRID
    grid_scale_x=1/5;
    for(i = vault_z/2) {
        for (v = [plate_w*grid_scale_x : plate_w*grid_scale_x : plate_w-plate_w*grid_scale_x]) { 
            // Wall 1 (Front)
            translate([v + wall_t, -5, i + wall_t]) 
            rotate([-90, 0, 0]) cylinder(h=20, d=4.5, $fn=6);
            
            // Wall 2 (Back)
            translate([v + wall_t, plate_h + wall_t - 5, i + wall_t]) 
            rotate([-90, 0, 0]) cylinder(h=20, d=4.5, $fn=6);
        }
    }  

}

// --- UNIVERSAL REINFORCED RECTANGULAR STANDOFF ---
module standoff(x, y, h=23) {
    translate([x, y, 0]) 
    difference() {
       
        // The Core: Now a square block for universal wall-fusion
        // Center it so the screw hole stays at (x,y)
        translate([-3, -3, 0]) 
            cube([6, 6, h]); 
            
           
        // The Screw Hole (Circular is better for threads)
        translate([0,0,0]) 
            cylinder(h=h+2, d=1.8, $fn=50); 
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
    standoff(lid_x + margin-wall_t, margin, pi_z);
    standoff(lid_x + margin-wall_t, plate_h-margin, pi_z);
    standoff(plate_w-margin, margin, pi_z);
    standoff(plate_w-margin, plate_h-margin, pi_z);
   
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

    //lip - negative version of box, but enlarged a little for clearance
    difference(){
        //remove material
        hull() {
            // Top-Left
            translate([ext_r, ext_r, wall_t]) 
                cylinder(r=ext_r+1, h=vault_z + wall_t, $fn=50);
            // Top-Right
            translate([plate_w + (wall_t*2) - ext_r, ext_r, wall_t]) 
                cylinder(r=ext_r+1, h=vault_z + wall_t, $fn=50);
            // Bottom-Left
            translate([ext_r, plate_h + (wall_t*2) - ext_r, wall_t]) 
                cylinder(r=ext_r+1, h=vault_z + wall_t, $fn=50);
            // Bottom-Right
            translate([plate_w + (wall_t*2) - ext_r, plate_h + (wall_t*2) - ext_r, wall_t]) 
                cylinder(r=ext_r+1, h=vault_z + wall_t, $fn=50);
        }


        // excluded from removal to create the lip
        translate([wall_t, wall_t, 0]) {
            hull() {
                // Internal Top-Left
                translate([ext_r-wall_t-lid_clearance, ext_r-wall_t-lid_clearance, 0]) 
                    cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
                // Internal Top-Right
                translate([plate_w - (ext_r-wall_t)-lid_clearance, ext_r-wall_t-lid_clearance, 0]) 
                    cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
                // Internal Bottom-Left
                translate([ext_r-wall_t-lid_clearance, plate_h - (ext_r-wall_t)-lid_clearance, 0]) 
                    cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
                // Internal Bottom-Right
                translate([plate_w - (ext_r-wall_t)-lid_clearance, plate_h - (ext_r-wall_t)-lid_clearance, 0]) 
                    cylinder(r=ext_r-wall_t, h=vault_z + 10, $fn=50);
            }
        }


    }
 

    
    // holes
    translate([lid_x + margin, margin+wall_t,-1])
    cylinder(h=lid_depth+10, d=2.9, $fn=50); 
    
    translate([lid_x + margin, plate_h+wall_t-margin,-1])
    cylinder(h=lid_depth+10, d=2.9, $fn=50); 
    
    translate([wall_t+plate_w-margin, margin+wall_t,-1])
    cylinder(h=lid_depth+10, d=2.9, $fn=50); 
    
    translate([wall_t+plate_w-margin, plate_h+wall_t-margin,-1])
    cylinder(h=lid_depth+10, d=2.9, $fn=50); 
    
    translate([lid_x + (plate_w-lid_x)/2, wall_t+plate_h/2,-1])
    cube([bayite_hole_w, bayite_hole_h, lid_depth+10], center=true);
    cylinder(h=lid_depth+10, d=2.9, $fn=50); 
  
}




